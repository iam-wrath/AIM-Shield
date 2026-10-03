"""FastAPI app: /chat/guard-only, /chat/shielded, /usage, /health."""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .attacks import load_attacks
from .assistant import SessionStore, build_system_prompt
from .config import Settings, get_settings
from .eventlog import EventLog
from .faults import FaultGuard, fail_open_result
from .guard_client import (
    GuardAuthError,
    GuardClient,
    GuardDailyQuotaExceeded,
    GuardError,
    GuardRateLimited,
    GuardTextRequired,
    GuardTextTooLong,
    GuardUnavailable,
)
from .layers import build_layers
from .llm_client import ChatMessage, LLMClient, LLMError, build_llm_client
from .models import ChatRequest, Decision, GuardOnlyResponse, ShieldedResponse
from .policy import ShieldPipeline
from .rag.store import RagStore, screen_chunks

USAGE_TTL = 5.0  # seconds; the UI polls /usage, so don't pass every poll to the Guard

_STATUS = {
    GuardAuthError: 502,  # our token is wrong: not the caller's fault
    GuardTextRequired: 400,
    GuardTextTooLong: 413,
    GuardRateLimited: 429,
    GuardDailyQuotaExceeded: 429,
    GuardUnavailable: 503,
}


def create_app(settings: Settings | None = None, llm: LLMClient | None = None,
               guard: GuardClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s = settings or get_settings()
        app.state.settings = s
        app.state.guard = guard or GuardClient(s)
        # The baseline route behaves like a naive app: its own client, no result cache.
        app.state.guard_naive = guard or GuardClient(s, cache=False)
        app.state.llm = llm or build_llm_client(s)
        app.state.sessions = SessionStore(s.session_history_limit)
        app.state.events = EventLog(s.db_path)
        app.state.rag = RagStore(s.rag_dir)
        inputs, outputs = build_layers(s)
        app.state.pipeline = ShieldPipeline(app.state.guard, app.state.llm,
                                            input_layers=inputs, output_layers=outputs)
        app.state.usage_cache = (0.0, None)
        dist = Path(s.frontend_dist)
        if dist.is_dir():  # built Attack Lab; mounted after the API routes so they win
            app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
        yield
        await app.state.guard.aclose()
        if app.state.guard_naive is not app.state.guard:
            await app.state.guard_naive.aclose()
        await app.state.llm.aclose()
        app.state.events.close()

    app = FastAPI(title="Aim Shield", lifespan=lifespan)

    @app.exception_handler(GuardError)
    async def _guard_error(_: Request, exc: GuardError):
        body = {"error": exc.code, "detail": str(exc)}
        headers = {}
        if isinstance(exc, GuardRateLimited) and exc.retry_after:
            body["retry_after"] = exc.retry_after
            headers["Retry-After"] = str(int(exc.retry_after) + 1)
        return JSONResponse(body, status_code=_STATUS.get(type(exc), 502), headers=headers)

    @app.exception_handler(LLMError)
    async def _llm_error(_: Request, exc: LLMError):
        return JSONResponse({"error": "llm_error", "detail": str(exc)}, status_code=502)

    @app.get("/health")
    async def health(deep: bool = False):
        out = {"status": "ok"}
        if deep:  # /health on the Guard needs no token and no quota
            out["guard"] = await app.state.guard.health()
        return out

    @app.get("/usage")
    async def usage():
        ts, data = app.state.usage_cache
        if data is None or time.monotonic() - ts > USAGE_TTL:
            data = await app.state.guard.usage()
            app.state.usage_cache = (time.monotonic(), data)
        return data

    @app.get("/attacks")
    async def attacks():
        return load_attacks(Path(app.state.settings.attacks_dir))

    @app.get("/replay")
    async def replay():
        f = Path(app.state.settings.eval_dir) / "results.json"
        if not f.is_file():
            return JSONResponse({"error": "no_replay", "detail": "eval/results.json not found"}, status_code=404)
        return json.loads(f.read_text(encoding="utf-8"))

    def _live_only() -> None:
        if getattr(app.state, "replay_only", False):
            raise HTTPException(503, getattr(app.state, "replay_message", "replay-only mode"))

    @app.post("/chat/guard-only", response_model=GuardOnlyResponse)
    async def chat_guard_only(req: ChatRequest):
        """Baseline: trusts the Guard's `allowed` flag exactly as a naive app would."""
        _live_only()
        t0 = time.perf_counter()
        st = app.state
        ms = lambda: round((time.perf_counter() - t0) * 1000, 1)  # noqa: E731

        naive = FaultGuard(req.simulate) if req.simulate else st.guard_naive
        try:
            gp = await naive.check_prompt(req.message)
        except GuardError:
            if not req.simulate:
                raise
            gp = fail_open_result("/v1/check/prompt")  # a typical app treats "no answer" as "not flagged"
        if not gp.allowed:
            st.events.record(session_id=req.session_id, mode="guard-only", stage="prompt",
                             decision="BLOCK", fired_layer="guard",
                             guard_request_id=gp.request_id, latency_ms=ms())
            return GuardOnlyResponse(reply=None, blocked=True, stage="prompt",
                                     guard_prompt=gp, total_latency_ms=ms())

        history = st.sessions.history("guard-only", req.session_id)
        history.append(_user(req.message))
        # A naive app puts retrieved text straight into the prompt, unchecked.
        context = [c.text for c in st.rag.retrieve(req.message)]
        reply = await st.llm.complete(history, system=build_system_prompt(
            st.settings.canary_token, context))

        try:
            gr = await naive.check_response(reply) if reply.strip() else None
        except GuardError:
            if not req.simulate:
                raise
            gr = fail_open_result("/v1/check/response")
        if gr is not None and not gr.allowed:
            st.events.record(session_id=req.session_id, mode="guard-only", stage="response",
                             decision="BLOCK", fired_layer="guard",
                             guard_request_id=gr.request_id, latency_ms=ms())
            return GuardOnlyResponse(reply=None, blocked=True, stage="response",
                                     guard_prompt=gp, guard_response=gr, total_latency_ms=ms())

        st.sessions.append_turn("guard-only", req.session_id, req.message, reply)
        st.events.record(session_id=req.session_id, mode="guard-only", stage="ok",
                         decision="ALLOW", guard_request_id=gp.request_id, latency_ms=ms())
        return GuardOnlyResponse(reply=reply, blocked=False, stage="ok", guard_prompt=gp,
                                 guard_response=gr, total_latency_ms=ms())

    @app.post("/chat/shielded", response_model=ShieldedResponse)
    async def chat_shielded(req: ChatRequest):
        _live_only()
        t0 = time.perf_counter()
        st = app.state
        ms = lambda: round((time.perf_counter() - t0) * 1000, 1)  # noqa: E731

        pipeline = st.pipeline
        if req.simulate:  # same layers, but the Guard fails the way we are demonstrating
            pipeline = ShieldPipeline(FaultGuard(req.simulate), st.llm,
                                      st.pipeline.input_layers, st.pipeline.output_layers)
        iv = await pipeline.screen_input(req.session_id, req.message)
        st.events.record(session_id=req.session_id, mode="shielded", stage="input",
                         decision=iv.decision.value, fired_layer=iv.fired_layer,
                         guard_request_id=iv.guard_raw.request_id if iv.guard_raw else None,
                         latency_ms=iv.total_latency_ms)
        if iv.decision is Decision.BLOCK:
            return ShieldedResponse(reply=f"{iv.reason} {iv.next_step}".strip(), blocked=True,
                                    input_verdict=iv, total_latency_ms=ms())

        message = iv.sanitized_text or req.message
        safe_chunks, rag_step = await screen_chunks(pipeline.guard, st.rag.retrieve(message))
        iv.trace.append(rag_step)
        iv.guard_calls += rag_step.guard_calls
        if rag_step.decision is Decision.WARN and iv.decision is Decision.ALLOW:
            iv.decision, iv.fired_layer, iv.reason = Decision.WARN, "rag_screen", rag_step.reason
        history = st.sessions.history("shielded", req.session_id)
        history.append(_user(message))
        reply = await st.llm.complete(history, system=build_system_prompt(
            st.settings.canary_token, [c.text for c in safe_chunks]))

        ov = await pipeline.screen_output(req.session_id, reply) if reply.strip() else None
        if ov is not None:
            st.events.record(session_id=req.session_id, mode="shielded", stage="output",
                             decision=ov.decision.value, fired_layer=ov.fired_layer,
                             guard_request_id=ov.guard_raw.request_id if ov.guard_raw else None,
                             latency_ms=ov.total_latency_ms)
            if ov.decision is Decision.BLOCK:
                return ShieldedResponse(reply=f"{ov.reason} {ov.next_step}".strip(), blocked=True,
                                        input_verdict=iv, output_verdict=ov, total_latency_ms=ms())
            reply = ov.sanitized_text or reply

        st.sessions.append_turn("shielded", req.session_id, message, reply)
        return ShieldedResponse(reply=reply, blocked=False, input_verdict=iv,
                                output_verdict=ov, total_latency_ms=ms())

    return app


def _user(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=text)


# Settings are read in the lifespan, so a missing GUARD_TOKEN fails clearly at startup.
app = create_app()

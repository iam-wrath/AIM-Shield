"""Layer pipeline: runs the Guard plus pluggable Aim layers and merges them into one Verdict.

The Guard step itself carries two Aim behaviours: the Chunker (text over 4,000 chars is checked
in overlapping windows) and the Fail-safe Policy (partial / unreachable Guard -> local checks
decide). Everything else is a Layer from layers/. A BLOCK short-circuits to save quota, and a
crashing layer blocks (fail closed).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from .guard_client import (
    MAX_TEXT_CHARS,
    GuardClient,
    GuardDailyQuotaExceeded,
    GuardError,
    GuardRateLimited,
    GuardTextTooLong,
    GuardUnavailable,
)
from .layers.base import (  # noqa: F401  (re-exported for callers and tests)
    GUARD_FLAG_TEXT,
    Layer,
    LayerContext,
    LayerResult,
    Side,
    flag_reason,
)
from .layers.chunker import MAX_WINDOWS, check_windows, chunk_text
from .layers.failsafe import decide_without_guard
from .llm_client import LLMClient
from .models import DECISION_RANK, Decision, GuardResult, TraceStep, Verdict


@dataclass
class _Acc:
    """Accumulates trace + the strongest decision while screening one text."""

    text: str
    trace: list[TraceStep] = field(default_factory=list)
    decision: Decision = Decision.ALLOW
    fired: str | None = None
    reason: str = ""
    next_step: str = ""
    sanitized: str | None = None
    guard_calls: int = 0
    degraded: bool = False

    def add(self, layer: str, res: LayerResult, ms: float) -> None:
        self.trace.append(TraceStep(layer=layer, decision=res.decision, reason=res.reason,
                                    latency_ms=round(ms, 1), guard_calls=res.guard_calls))
        self.guard_calls += res.guard_calls
        if res.sanitized_text is not None:
            self.text = self.sanitized = res.sanitized_text
        if DECISION_RANK[res.decision] > DECISION_RANK[self.decision]:
            self.decision, self.fired = res.decision, layer
            self.reason, self.next_step = res.reason, res.next_step


class ShieldPipeline:
    def __init__(
        self,
        guard: GuardClient,
        llm: LLMClient | None = None,
        input_layers: Sequence[Layer] = (),
        output_layers: Sequence[Layer] = (),
    ):
        self.guard = guard
        self.llm = llm
        self.input_layers: list[Layer] = list(input_layers)
        self.output_layers: list[Layer] = list(output_layers)

    async def screen_input(self, session_id: str, text: str) -> Verdict:
        return await self._screen("input", session_id, text)

    async def screen_output(self, session_id: str, text: str) -> Verdict:
        return await self._screen("output", session_id, text)

    # ---- internals --------------------------------------------------------------

    async def _screen(self, side: Side, session_id: str, text: str) -> Verdict:
        t0 = time.perf_counter()
        acc = _Acc(text=text)
        guard_result = await self._guard_step(side, text, acc)

        if acc.decision is not Decision.BLOCK:  # a BLOCK short-circuits: saves quota
            layers = self.input_layers if side == "input" else self.output_layers
            for layer in layers:
                ctx = LayerContext(session_id, acc.text, side, self.guard, self.llm, guard_result, text)
                start = time.perf_counter()
                try:
                    res = await layer.run(ctx)
                except (GuardRateLimited, GuardDailyQuotaExceeded, GuardUnavailable):
                    res = decide_without_guard(
                        acc.text, f"The Guard could not be reached for the '{layer.name}' check.")
                except Exception as exc:  # a broken layer must not fail open
                    res = LayerResult(
                        Decision.BLOCK,
                        f"Safety layer '{layer.name}' failed ({type(exc).__name__}); blocking to be safe.",
                        "Try again in a moment.",
                    )
                acc.add(layer.name, res, (time.perf_counter() - start) * 1000)
                if acc.decision is Decision.BLOCK:
                    break

        return Verdict(
            decision=acc.decision,
            fired_layer=acc.fired,
            reason=acc.reason or "No risk found.",
            next_step=acc.next_step,
            sanitized_text=acc.sanitized,
            guard_raw=guard_result,
            trace=acc.trace,
            total_latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            guard_calls=acc.guard_calls,
            degraded=acc.degraded,
        )

    def _judge(self, text: str, result: GuardResult, note: str = "") -> LayerResult:
        if not result.allowed:
            return LayerResult(Decision.BLOCK, flag_reason(result) + note,
                               "Rephrase your message and try again.")
        if result.is_partial:
            why = (f"The Guard returned a partial result (checks not run: "
                   f"{', '.join(result.checks_not_run) or 'unknown'}).")
            return decide_without_guard(text, why)
        return LayerResult(reason=note.strip())

    async def _guard_step(self, side: Side, text: str, acc: _Acc) -> GuardResult | None:
        start = time.perf_counter()
        call = self.guard.check_prompt if side == "input" else self.guard.check_response
        name, result, calls = "guard", None, 0
        try:
            if len(text) > MAX_TEXT_CHARS:
                windows = chunk_text(text)
                name = "chunker"
                if len(windows) > MAX_WINDOWS:
                    res = LayerResult(
                        Decision.BLOCK,
                        f"The text is {len(text):,} characters, too long to check safely.",
                        "Send a shorter message or split it into parts.")
                else:
                    result, calls = await check_windows(call, windows)
                    res = self._judge(text, result, f" (checked in {len(windows)} overlapping windows)")
            else:
                result = await call(text)
                calls = 0 if result.cached else 1
                res = self._judge(text, result)
        except (GuardRateLimited, GuardDailyQuotaExceeded, GuardUnavailable) as exc:
            name = "failsafe"
            why = {
                "rate_limited": "The Guard is rate limiting requests.",
                "daily_quota_exceeded": "The Guard's daily quota is used up.",
            }.get(exc.code, "The Guard could not be reached.")
            res = decide_without_guard(text, why)
        except GuardTextTooLong:
            res = LayerResult(Decision.BLOCK, "The text is too long for the Guard.",
                              "Send a shorter message.")
        except GuardError as exc:  # auth error, bad request: nothing safe to infer
            res = LayerResult(Decision.BLOCK, f"The Guard check failed ({exc.code}); blocking to be safe.",
                              "Try again in a moment.")
        res.guard_calls = calls
        acc.degraded = name == "failsafe" or (result is not None and result.is_partial)
        acc.add(name, res, (time.perf_counter() - start) * 1000)
        return result

"""LLM adapter interface plus one OpenAI-compatible implementation."""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

from .config import Settings


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class LLMError(Exception):
    pass


class LLMClient(ABC):
    """Swap implementations here if the organisers' LLM API is not OpenAI-shaped."""

    @abstractmethod
    async def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str: ...

    async def complete_with_tools(self, messages: list[ChatMessage], *, system: str | None, tools: list[dict],
                                  run_tool) -> str:
        """Chat with function calling. Default: ignore tools (implementations override)."""
        return await self.complete(messages, system=system)

    async def aclose(self) -> None:  # optional
        return None


class OpenAICompatibleClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0,
                 http: httpx.AsyncClient | None = None):
        self._url = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    # TODO(LLM API shape): the organisers' request/response format is unknown.
    # Everything shape-specific lives in these three methods; adjust them (or add a
    # new LLMClient subclass and register it in build_llm_client) once confirmed.
    def _endpoint(self) -> str:
        if self._url.endswith("/chat/completions"):
            return self._url
        return f"{self._url}/chat/completions"

    def _build_payload(self, messages: list[ChatMessage], system: str | None) -> dict[str, Any]:
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": m.role, "content": m.content} for m in messages
        ]
        return {"model": self._model, "messages": msgs, "temperature": 0.2}

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("unexpected LLM response shape") from None

    async def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str:
        data = await self._post(self._build_payload(messages, system))
        return self._parse_response(data)

    async def complete_with_tools(self, messages: list[ChatMessage], *, system: str | None, tools: list[dict],
                                  run_tool, max_rounds: int = 4) -> str:
        msgs: list[dict] = ([{"role": "system", "content": system}] if system else []) + [
            {"role": m.role, "content": m.content} for m in messages]
        for _ in range(max_rounds):
            data = await self._post({"model": self._model, "messages": msgs, "tools": tools, "temperature": 0.2})
            try:
                msg = data["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                raise LLMError("unexpected LLM response shape") from None
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content") or ""
            msgs.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
            for c in calls:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                result = await run_tool(c["function"]["name"], args if isinstance(args, dict) else {})
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": result})
        data = await self._post({"model": self._model, "messages": msgs, "temperature": 0.2})  # no more tools
        return self._parse_response(data)

    async def _post(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        for attempt in range(2):  # one retry for timeouts, 429 and 5xx
            try:
                resp = await self._http.post(self._endpoint(), json=payload, headers=headers)
            except httpx.TransportError as exc:
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise LLMError(f"LLM network error: {type(exc).__name__}") from None
            if resp.status_code in (429, 500, 502, 503) and attempt == 0:
                await asyncio.sleep(1.0)
                continue
            if resp.status_code != 200:
                raise LLMError(f"LLM returned HTTP {resp.status_code}")
            return resp.json()
        raise LLMError("LLM request failed")  # unreachable; keeps type checkers happy


def build_llm_client(settings: Settings) -> LLMClient:
    if not settings.llm_url or not settings.llm_model:
        raise LLMError("LLM_URL and LLM_MODEL must be set in .env")
    return OpenAICompatibleClient(
        settings.llm_url, settings.llm_key.get_secret_value(), settings.llm_model,
        settings.llm_timeout,
    )

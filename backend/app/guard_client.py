"""Async client for the SecureAI Guard API.

Handles every documented error code, enforces the 4,000-char limit locally,
caches complete results by SHA-256 of (endpoint, text) and records latency.
The token is only ever placed in the Authorization header; it is never logged.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Awaitable, Callable

import httpx

from .config import Settings
from .models import GuardResult

MAX_TEXT_CHARS = 4000
PROMPT_PATH = "/v1/check/prompt"
RESPONSE_PATH = "/v1/check/response"
USAGE_PATH = "/v1/usage"
HEALTH_PATH = "/health"


class GuardError(Exception):
    """Base class for all Guard client errors."""

    code = "guard_error"

    def __init__(self, message: str = "", *, status_code: int | None = None):
        super().__init__(message or self.code)
        self.status_code = status_code


class GuardAuthError(GuardError):  # 401
    code = "unauthorized"


class GuardTextRequired(GuardError):  # 400
    code = "text_required"


class GuardTextTooLong(GuardError):  # 413 or local pre-check
    code = "text_too_long"


class GuardRateLimited(GuardError):  # 429 rate_limited, waits exhausted
    code = "rate_limited"

    def __init__(self, message: str = "", *, retry_after: float | None = None,
                 status_code: int | None = 429):
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


class GuardDailyQuotaExceeded(GuardError):  # 429 daily_quota_exceeded (resets 00:00 UTC)
    code = "daily_quota_exceeded"


class GuardUnavailable(GuardError):  # 502 guard_unavailable / 503 service_busy / network
    code = "guard_unavailable"


def _error_code(resp: httpx.Response) -> str:
    """Best-effort extraction of the Guard's error code from the JSON body."""
    # TODO(confirm Friday): the exact error body shape; this handles the common ones.
    try:
        body = resp.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        err = body.get("error", body.get("code", ""))
        if isinstance(err, dict):
            err = err.get("code", "")
        return str(err or "")
    return ""


def _retry_after(resp: httpx.Response, default: float = 2.0) -> float:
    raw = resp.headers.get("Retry-After")
    try:
        return max(0.0, float(raw)) if raw is not None else default
    except ValueError:
        return default  # HTTP-date form is not expected from this API


class GuardClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        cache: bool = True,
    ):
        self._s = settings
        self._http = http or httpx.AsyncClient(
            base_url=settings.guard_url, timeout=settings.guard_timeout
        )
        self._sleep = sleep
        self._use_cache = cache
        self._cache: dict[str, GuardResult] = {}
        self.calls = 0  # HTTP requests actually sent (retries included)

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---- public API -------------------------------------------------------------

    async def check_prompt(self, text: str) -> GuardResult:
        return await self._check(PROMPT_PATH, text)

    async def check_response(self, text: str) -> GuardResult:
        return await self._check(RESPONSE_PATH, text)

    async def usage(self) -> dict[str, Any]:
        return await self._request("GET", USAGE_PATH)

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", HEALTH_PATH, auth=False)

    # ---- internals --------------------------------------------------------------

    async def _check(self, path: str, text: str) -> GuardResult:
        if not text or not text.strip():
            raise GuardTextRequired("text must not be empty")
        if len(text) > MAX_TEXT_CHARS:
            raise GuardTextTooLong(f"{len(text)} chars exceeds the {MAX_TEXT_CHARS}-char limit")

        key = hashlib.sha256(f"{path}\0{text}".encode("utf-8")).hexdigest()
        hit = self._cache.get(key) if self._use_cache else None
        if hit is not None:
            return hit.model_copy(update={"cached": True, "round_trip_ms": 0.0})

        start = time.perf_counter()
        data = await self._request("POST", path, json={"text": text})
        result = GuardResult.model_validate(data)
        result.endpoint = path
        result.round_trip_ms = (time.perf_counter() - start) * 1000

        if self._use_cache and not result.is_partial:  # a partial result may be better on retry; don't pin it
            self._cache[key] = result
        return result

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._s.guard_token.get_secret_value()}"
        return headers

    async def _request(
        self, method: str, path: str, *, json: dict | None = None, auth: bool = True
    ) -> dict[str, Any]:
        s = self._s
        retries = 0
        rate_waits = 0
        while True:
            self.calls += 1
            try:
                resp = await self._http.request(
                    method, path, json=json, headers=self._headers(auth)
                )
            except httpx.TransportError as exc:
                if retries >= s.guard_max_retries:
                    raise GuardUnavailable(f"network error: {type(exc).__name__}") from None
                await self._sleep(s.guard_backoff_base * 2**retries)
                retries += 1
                continue

            code = resp.status_code
            if code == 200:
                return resp.json()
            err = _error_code(resp)
            if code == 400:
                raise GuardTextRequired(err or "bad request", status_code=code)
            if code == 401:
                raise GuardAuthError("Guard rejected the token (401)", status_code=code)
            if code == 413:
                raise GuardTextTooLong(err or "text too long", status_code=code)
            if code == 429:
                if "daily_quota" in err:
                    raise GuardDailyQuotaExceeded(
                        "daily quota exceeded; resets 00:00 UTC", status_code=code
                    )
                wait = _retry_after(resp)
                if rate_waits >= s.guard_max_rate_limit_waits or wait > s.guard_max_retry_after:
                    raise GuardRateLimited("rate limited", retry_after=wait)
                rate_waits += 1
                await self._sleep(wait)
                continue
            if code in (502, 503):
                if retries >= s.guard_max_retries:
                    raise GuardUnavailable(err or f"Guard unavailable ({code})", status_code=code)
                await self._sleep(s.guard_backoff_base * 2**retries)
                retries += 1
                continue
            raise GuardError(err or f"unexpected status {code}", status_code=code)

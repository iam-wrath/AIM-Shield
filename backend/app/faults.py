"""Demo-only fault injection: a Guard stand-in that fails the way the real one can (W4).

Selected per request with `simulate` ("outage" or "partial"). It makes no network call, so it
costs no quota. Real outages and `partial` results are rare, so this is how we show the
fail-open weakness on demand.
"""
from __future__ import annotations

from .guard_client import GuardUnavailable
from .models import GuardCheck, GuardResult

CATEGORIES = ("injection", "harmful_content", "sensitive_data", "unsafe_links", "prohibited_content")


class FaultGuard:
    def __init__(self, mode: str):
        self.mode = mode
        self.calls = 0

    async def _check(self, endpoint: str) -> GuardResult:
        if self.mode == "outage":
            raise GuardUnavailable("simulated Guard outage (502)", status_code=502)
        # partial: nothing flagged, but the checks did not run
        return GuardResult(
            allowed=True, flags=[], status="partial",
            checks={c: GuardCheck(ran=False) for c in CATEGORIES},
            request_id="simulated", latency_ms=0.0, endpoint=endpoint, round_trip_ms=0.0,
            cached=True)  # cached=True so it is not counted as a real Guard call

    async def check_prompt(self, text: str) -> GuardResult:
        return await self._check("/v1/check/prompt")

    async def check_response(self, text: str) -> GuardResult:
        return await self._check("/v1/check/response")


def fail_open_result(endpoint: str) -> GuardResult:
    """What a naive app records when the Guard gives no answer: nothing flagged, so allowed."""
    return GuardResult(allowed=True, flags=[], status="unavailable", checks={},
                       request_id="simulated-outage", latency_ms=0.0, endpoint=endpoint, round_trip_ms=0.0)

"""Shared pydantic models: Guard results, Verdict, API request/response bodies."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GuardCheck(BaseModel):
    model_config = ConfigDict(extra="allow")
    ran: bool = True
    flagged: bool = False
    confidence: str | None = None
    types: list[str] = Field(default_factory=list)


class GuardResult(BaseModel):
    """Typed form of the Guard's check response, plus a few local fields."""

    model_config = ConfigDict(extra="allow")

    allowed: bool
    flags: list[str] = Field(default_factory=list)
    status: str = "complete"  # "complete" | "partial"
    checks: dict[str, GuardCheck] = Field(default_factory=dict)
    request_id: str | None = None
    latency_ms: float | None = None  # reported by the Guard

    # filled in locally by GuardClient
    endpoint: str | None = None
    cached: bool = False
    round_trip_ms: float | None = None  # our measured wall time (0 on cache hit)

    @property
    def is_partial(self) -> bool:
        return self.status != "complete"

    @property
    def checks_not_run(self) -> list[str]:
        return [name for name, c in self.checks.items() if not c.ran]

    @property
    def top_confidence(self) -> str | None:
        for c in self.checks.values():
            if c.flagged and c.confidence:
                return c.confidence
        return None


class Decision(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


DECISION_RANK = {Decision.ALLOW: 0, Decision.WARN: 1, Decision.REDACT: 2, Decision.BLOCK: 3}


class TraceStep(BaseModel):
    layer: str
    decision: Decision  # ALLOW=green, WARN/REDACT=amber, BLOCK=red in the UI
    reason: str = ""
    latency_ms: float = 0.0
    guard_calls: int = 0


class Verdict(BaseModel):
    decision: Decision
    fired_layer: str | None = None  # layer behind the decision; None when ALLOW
    reason: str = ""
    next_step: str = ""
    sanitized_text: str | None = None  # set when a layer redacted/normalised the text
    guard_raw: GuardResult | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    guard_calls: int = 0


# ---- API bodies -----------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)
    simulate: Literal["outage", "partial"] | None = None  # demo: pretend the Guard fails (W4)


class GuardOnlyResponse(BaseModel):
    reply: str | None  # None when the Guard stopped it
    blocked: bool
    stage: str  # "prompt" | "response" | "ok"
    guard_prompt: GuardResult
    guard_response: GuardResult | None = None
    total_latency_ms: float


class ShieldedResponse(BaseModel):
    reply: str
    blocked: bool
    input_verdict: Verdict
    output_verdict: Verdict | None = None
    total_latency_ms: float

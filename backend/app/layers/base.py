"""Layer interface shared by the pipeline (policy.py) and every Aim layer.

Kept free of imports from policy.py so layers and the pipeline can import each other's
helpers without a cycle.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from ..guard_client import GuardClient
from ..llm_client import LLMClient
from ..models import Decision, GuardResult

Side = Literal["input", "output"]

GUARD_FLAG_TEXT = {
    "injection": "It looks like an attempt to override the assistant's instructions.",
    "harmful_content": "It asks for or contains harmful content.",
    "sensitive_data": "It contains sensitive personal or credential data.",
    "unsafe_links": "It contains an unsafe link.",
    "prohibited_content": "It contains content this service does not allow.",
}


def flag_reason(result: GuardResult) -> str:
    return " ".join(GUARD_FLAG_TEXT.get(f, f"Flagged: {f}.") for f in result.flags) or "Flagged by the Guard."


@dataclass
class LayerContext:
    session_id: str
    text: str  # current text (earlier layers may have redacted/normalised it)
    side: Side
    guard: GuardClient
    llm: LLMClient | None = None
    guard_result: GuardResult | None = None  # the primary Guard check of this text


@dataclass
class LayerResult:
    decision: Decision = Decision.ALLOW
    reason: str = ""
    next_step: str = ""
    sanitized_text: str | None = None
    guard_calls: int = 0


class Layer(ABC):
    name: str = "layer"
    side: Side = "input"

    @abstractmethod
    async def run(self, ctx: LayerContext) -> LayerResult: ...

"""Fail-safe Policy (W4): decide with local checks when the Guard gives no full answer.

A `partial` result or an unreachable Guard must not mean an open door: local checks (Ghana Lens
secrets plus injection phrases, on the raw and the canonicalised text) decide. High risk blocks;
otherwise the message goes through with a visible WARN. The same local checks screen retrieved
RAG passages, and `solicits_secret` also guards the model's answers (Output Sentinel).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import Decision
from . import ghana_lens
from .base import LayerResult
from .canonicaliser import canonicalise

INJECTION_PATTERNS = [
    re.compile(p, re.I) for p in (
        r"\b(?:ignore|disregard|forget|override)\b.{0,40}\b(?:previous|prior|above|earlier|all|your)\b.{0,30}\b(?:instruction|rule|prompt|guideline)s?",
        r"\b(?:reveal|show|print|repeat|leak|tell me)\b.{0,40}\b(?:system prompt|hidden prompt|instructions|secret|canary)",
        r"\b(?:jailbreak|developer mode|do anything now|dan mode)\b",
        r"\byou are now\b.{0,40}\b(?:unrestricted|free|no rules|without restrictions)",
        r"\bpretend\b.{0,30}\bno (?:rules|restrictions|filters)",
    )
]

# "send your MoMo PIN to ..." style social engineering (the Guard allowed these in probes).
SOLICIT = re.compile(
    r"\b(?:send|share|give|tell|enter|provide|submit|text|reply|confirm|verify|type|forward|disclose)\w*\b"
    r"[^.\n]{0,80}?\b(?:pin|password|passcode|otp|one[- ]time (?:code|password))\b",
    re.I,
)
# A sentence that warns about this ("never share your PIN", "if someone asks ... it's a scam") is advice, not a request.
CAUTION = re.compile(
    r"\b(?:never|don'?t|do not|doesn'?t|does not|won'?t|will not|should not|shouldn'?t|avoid|"
    r"if (?:someone|anyone|a caller|a person)|scammers?|fraudsters?|criminals?|attackers?|"
    r"(?:is|it'?s|are) a scam)\b",
    re.I,
)
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def solicits_secret(text: str) -> bool:
    """True when a sentence asks the reader to hand over a PIN/password (warnings against it are fine)."""
    for sentence in SENTENCE.split(text):
        if SOLICIT.search(sentence) and not CAUTION.search(sentence):
            return True
    return False


@dataclass
class LocalRisk:
    high: bool = False
    reasons: list[str] = field(default_factory=list)


def local_risk(text: str) -> LocalRisk:
    risk = LocalRisk()
    variants = [text, canonicalise(text).text]
    for v in variants:
        for p in ghana_lens.scan(v):
            if p.kind == "credential" and p.label not in risk.reasons:
                risk.reasons.append(p.label)
        for pat in INJECTION_PATTERNS:
            if pat.search(v) and "instruction-override phrase" not in risk.reasons:
                risk.reasons.append("instruction-override phrase")
        if solicits_secret(v) and "request for a PIN or password" not in risk.reasons:
            risk.reasons.append("request for a PIN or password")
    risk.high = bool(risk.reasons)
    return risk


def decide_without_guard(text: str, why: str) -> LayerResult:
    risk = local_risk(text)
    if risk.high:
        return LayerResult(
            Decision.BLOCK,
            f"{why} Local checks found: {', '.join(risk.reasons)}.",
            "Rephrase your message and try again.",
        )
    return LayerResult(
        Decision.WARN,
        f"{why} Local checks found nothing, so the message continues with caution.",
        "",
    )

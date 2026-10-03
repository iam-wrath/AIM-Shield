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
    r"[^.\n]{0,80}?\b(?:pin|password|passcode)\b",
    re.I,
)
# Typing a one-time code into the support chat is the normal flow. Sending it to a number is the attack.
SOLICIT_OTP = re.compile(
    r"\b(?:send|share|forward|give|tell|read|text)\w*\b[^.\n]{0,60}\b(?:otp|one[- ]time (?:code|password)|code)\b"
    r"[^.\n]{0,40}\bto\b\s*(?:\+?\d|(?:this|that|the|another) number)",
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
        if (SOLICIT.search(sentence) or SOLICIT_OTP.search(sentence)) and not CAUTION.search(sentence):
            return True
    return False


# Asking the customer for a whole card number is never part of a KwikPay flow.
ASK_CARD = re.compile(
    r"\b(?:send|share|give|tell|enter|provide|submit|type|confirm|read)\w*\b[^.\n]{0,60}"
    r"\b(?:full\s+|complete\s+|whole\s+)?(?:debit\s+|credit\s+|ghana\s+)?card\s+(?:number|details|no\b)",
    re.I,
)
# What a hijacked agent says: money sent to a stranger, or verification skipped.
SOCIAL_ENGINEERING = [
    re.compile(p, re.I) for p in (
        r"\bsend\w*\s+(?:the\s+)?(?:money|funds|it|am|amount|payment)\s+back\s+to\s+(?:\+?\d|(?:this|that|the following|another|a)\s+number)",
        r"\breverse\w*\b[^.\n]{0,40}\bto\s+(?:\+?\d|(?:this|that|another|the following|a)\s+number)",
        r"\b(?:no|without)\s+(?:need\s+(?:for|to)\s+)?(?:identity\s+)?verif\w+|\bskip\w*\s+(?:the\s+)?verif\w+",
        r"\b(?:transfer|send|pay)\w*\b[^.\n]{0,40}\bto\s+(?:this|that|the following)\s+number\b[^.\n]{0,60}\b(?:confirm|verify|secure)",
    )
]


def asks_for_card_number(text: str) -> bool:
    return any(ASK_CARD.search(s) and not CAUTION.search(s) for s in SENTENCE.split(text))


def social_engineering(text: str) -> bool:
    """True when a sentence tells someone to move money to a stranger or skip verification."""
    return any(any(p.search(s) for p in SOCIAL_ENGINEERING) and not CAUTION.search(s) for s in SENTENCE.split(text))


@dataclass
class LocalRisk:
    high: bool = False
    reasons: list[str] = field(default_factory=list)


def local_risk(text: str) -> LocalRisk:
    risk = LocalRisk()
    variants = [text, canonicalise(text).text]
    for v in variants:
        for p in ghana_lens.scan(v):
            if p.kind in ("credential", "pin") and p.label not in risk.reasons:
                risk.reasons.append(p.label)
        for pat in INJECTION_PATTERNS:
            if pat.search(v) and "instruction-override phrase" not in risk.reasons:
                risk.reasons.append("instruction-override phrase")
        if solicits_secret(v) and "request for a PIN or password" not in risk.reasons:
            risk.reasons.append("request for a PIN or password")
        if social_engineering(v) and "social-engineering instruction" not in risk.reasons:
            risk.reasons.append("social-engineering instruction")
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

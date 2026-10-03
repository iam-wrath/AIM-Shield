"""Output Sentinel (W6): what the model says is checked against what a real support agent would never say.

Runs after the Guard's /check/response (pipeline) and alongside Ghana Lens on the reply. Checks:
  1. canary / system-prompt leak (internal reversal code, even spaced out or disguised)
  2. ask policy: a PIN or password, a whole card number, a one-time code sent to a number
  3. social-engineering patterns: "send the money back to this number", "no verification needed"
The Guard's own response check let all of these through in our probes (r-1, r-2, w6b-2).
"""
from __future__ import annotations

import re

from ..models import Decision
from .base import Layer, LayerContext, LayerResult
from .failsafe import asks_for_card_number, social_engineering, solicits_secret


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class OutputSentinel(Layer):
    name = "output_sentinel"
    side = "output"

    def __init__(self, canary: str):
        self._canary = _squash(canary)

    async def run(self, ctx: LayerContext) -> LayerResult:
        squashed = _squash(ctx.text)
        if (self._canary and self._canary in squashed) or "internalreversalcode" in squashed:
            return LayerResult(
                Decision.BLOCK,
                "The answer would have revealed the assistant's hidden instructions or internal code.",
                "Ask about your KwikPay account or a transaction instead.",
            )
        if solicits_secret(ctx.text):
            return LayerResult(
                Decision.BLOCK,
                "The answer asks you to hand over a PIN, password or one-time code. KwikPay and real banks never ask for these.",
                "Do not share it. If a document told the assistant to ask, report that document.",
            )
        if asks_for_card_number(ctx.text):
            return LayerResult(
                Decision.BLOCK,
                "The answer asks for a full card number, which is never part of a KwikPay support flow.",
                "Do not share card details in chat.",
            )
        if social_engineering(ctx.text):
            return LayerResult(
                Decision.BLOCK,
                "The answer tells you to send money to another number or to skip verification, which is how scams work.",
                "Do not send money. KwikPay never asks you to reverse or return funds to a different number.",
            )
        return LayerResult()

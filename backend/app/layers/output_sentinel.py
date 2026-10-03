"""Output Sentinel (W6): catch system-prompt / canary leakage in the model's answer.

Runs after the Guard's /check/response (pipeline) and alongside Ghana Lens redaction.
"""
from __future__ import annotations

import re

from ..models import Decision
from .base import Layer, LayerContext, LayerResult
from .failsafe import solicits_secret


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class OutputSentinel(Layer):
    name = "output_sentinel"
    side = "output"

    def __init__(self, canary: str):
        self._canary = _squash(canary)

    async def run(self, ctx: LayerContext) -> LayerResult:
        squashed = _squash(ctx.text)
        if (self._canary and self._canary in squashed) or "internalreferencecode" in squashed:
            return LayerResult(
                Decision.BLOCK,
                "The answer would have revealed the assistant's hidden instructions or secret code.",
                "Ask a question about your studies instead.",
            )
        if solicits_secret(ctx.text):
            return LayerResult(
                Decision.BLOCK,
                "The answer asks you to hand over a PIN or password. No real bank, network operator or university ever asks for these.",
                "Do not share it. If a document told the assistant to ask, report that document.",
            )
        return LayerResult()

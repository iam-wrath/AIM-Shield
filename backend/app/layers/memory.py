"""Conversation Memory (W2): catch payloads split across turns.

Keeps the last N user turns per session. When the new message contains a fragment cue
("part A", "combine", a variable assignment ...) it checks, in order:
  1. the quoted fragments joined into one clean string (the Guard flags this form on its own,
     but was seen to let the same text through once benign words were appended), then
  2. the stitched window of recent turns.
Once a session has been blocked here, later cue messages in it are blocked without a Guard call.
"""
from __future__ import annotations

import re
from collections import defaultdict, deque

from ..guard_client import MAX_TEXT_CHARS
from ..models import Decision
from .base import Layer, LayerContext, LayerResult, flag_reason

CUE = re.compile(
    r"\bpart\s+[a-z0-9]\b|\bcombine\b|\bconcatenat\w*|\bjoin\s+(?:them|these|the|part)\b|"
    r"\bput\s+(?:them|it|these)\s+together\b|\bcontinue\b|\bnow\s+(?:follow|do|run|execute)\b|"
    r"\bfollow\s+(?:a|the)\s*(?:\+|and)\s*b\b|"
    r"\b[a-z_]\w*\s*=\s*[\"'`]|\bstep\s*\d\b|\bremember\s+(?:this|that)\b|\bfrom\s+before\b",
    re.I,
)

QUOTED = re.compile(r"[\"'`]([^\"'`\n]{4,})[\"'`]")  # 4+ chars: skips throwaway quotes like "ok"


class ConversationMemory(Layer):
    name = "conversation_memory"
    side = "input"

    def __init__(self, turns: int = 5):
        self._turns: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=turns))
        self._tainted: set[str] = set()

    async def run(self, ctx: LayerContext) -> LayerResult:
        prior = list(self._turns[ctx.session_id])
        self._turns[ctx.session_id].append(ctx.text)  # record before checking
        if not prior or not CUE.search(ctx.text):
            return LayerResult()

        if ctx.session_id in self._tainted:
            return LayerResult(
                Decision.BLOCK,
                "Earlier messages in this conversation were assembling an unsafe request, "
                "and this one continues that pattern.",
                "Start a new conversation and ask your question directly.",
            )

        turns = prior + [ctx.text]
        candidates: list[tuple[str, str]] = []
        parts = [seg.strip() for t in turns for seg in QUOTED.findall(t)]
        if len(parts) >= 2:
            candidates.append(("the joined fragments", " ".join(parts)[:MAX_TEXT_CHARS]))
        candidates.append((f"your last {len(turns)} messages", "\n".join(turns)[-MAX_TEXT_CHARS:]))

        calls = 0
        for what, text in candidates:
            result = await ctx.guard.check_prompt(text)
            calls += 0 if result.cached else 1
            if not result.allowed:
                self._tainted.add(ctx.session_id)
                return LayerResult(
                    Decision.BLOCK,
                    f"Taken together, {what} form something unsafe: {flag_reason(result)} "
                    "Each message looked fine alone.",
                    "Ask for what you need in one clear, safe question.",
                    guard_calls=calls,
                )
        return LayerResult(guard_calls=calls)

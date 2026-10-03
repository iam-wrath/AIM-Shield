"""Ghana Lens (W1): format checks for Ghana-specific data and non-Google API keys.

Patterns live in data/ghana_patterns.json. Input: credentials block, other identifiers are
masked. Output: everything found is masked. Costs no Guard quota.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models import Decision
from .base import Layer, LayerContext, LayerResult, Side

PATTERNS_FILE = Path(__file__).parent / "data" / "ghana_patterns.json"


@dataclass(frozen=True)
class Pattern:
    name: str
    kind: str  # "credential" | "pii"
    label: str
    regex: re.Pattern


@lru_cache
def load_patterns(path: Path = PATTERNS_FILE) -> tuple[Pattern, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))["patterns"]
    return tuple(Pattern(p["name"], p["kind"], p["label"], re.compile(p["regex"])) for p in raw)


def scan(text: str) -> list[Pattern]:
    """Patterns that match anywhere in text (one entry per pattern)."""
    return [p for p in load_patterns() if p.regex.search(text)]


def redact(text: str) -> str:
    for p in load_patterns():
        text = p.regex.sub(f"[REDACTED:{p.name}]", text)
    return text


class GhanaLens(Layer):
    name = "ghana_lens"

    def __init__(self, side: Side = "input"):
        self.side = side

    async def run(self, ctx: LayerContext) -> LayerResult:
        hits = scan(ctx.text)
        if not hits:
            return LayerResult()
        labels = ", ".join(sorted({p.label for p in hits}))
        if self.side == "input" and any(p.kind == "credential" for p in hits):
            return LayerResult(
                Decision.BLOCK,
                f"The message contains a secret ({labels}). Secrets should never be pasted into a chat.",
                "Remove the PIN or key and ask your question again. If it is real, change it now.",
            )
        where = "before it reached the assistant" if self.side == "input" else "before you saw it"
        return LayerResult(
            Decision.REDACT,
            f"Sensitive data ({labels}) was masked {where}.",
            "Avoid sharing personal identifiers in chat.",
            sanitized_text=redact(ctx.text),
        )

"""Ghana Lens (W1): Ghana-specific data and non-Google API keys, on both sides. Costs no Guard quota.

Patterns live in data/ghana_patterns.json; each has a kind:
  pii         Ghana Card, MoMo number, TIN, KNUST IDs  -> masked
  pin         a MoMo / account PIN                     -> masked, with "KwikPay will never ask for your PIN"
  credential  API keys (sk-, ghp_, AKIA)               -> input is blocked, output is masked
  id          KwikPay transaction IDs                  -> never masked on input (the agent needs them);
                                                         on output masked unless they belong to the customer

Input also routes the one-time code: if a code was sent and the customer typed it, the mock verifier
raises the session's trust level and the model only ever sees "[OTP]". Output keeps the logged-in
customer's own identifiers and masks everyone else's.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from ..kwikpay import OTP_CODE, AuthStore, owns_card, owns_number, owns_txn, try_verify
from ..models import Decision
from .base import Layer, LayerContext, LayerResult, Side

PATTERNS_FILE = Path(__file__).parent / "data" / "ghana_patterns.json"
INPUT_MASK = {"pii", "pin"}
OUTPUT_MASK = {"pii", "pin", "credential", "id"}


@dataclass(frozen=True)
class Pattern:
    name: str
    kind: str
    label: str
    regex: re.Pattern


@lru_cache
def load_patterns(path: Path = PATTERNS_FILE) -> tuple[Pattern, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))["patterns"]
    return tuple(Pattern(p["name"], p["kind"], p["label"], re.compile(p["regex"])) for p in raw)


def scan(text: str) -> list[Pattern]:
    """Patterns that match anywhere in text (one entry per pattern)."""
    return [p for p in load_patterns() if p.regex.search(text)]


def find(text: str) -> list[tuple[Pattern, str]]:
    return [(p, m.group(0)) for p in load_patterns() for m in p.regex.finditer(text)]


Keep = Callable[[Pattern, str], bool]


def redact(text: str, kinds: set[str] | None = None, keep: Keep | None = None) -> str:
    kinds = kinds or {"pii", "pin", "credential"}
    for p in load_patterns():
        if p.kind not in kinds:
            continue
        text = p.regex.sub(
            lambda m, p=p: m.group(0) if keep and keep(p, m.group(0)) else f"[REDACTED:{p.name}]", text)
    return text


class GhanaLens(Layer):
    name = "ghana_lens"

    def __init__(self, side: Side = "input", auth: AuthStore | None = None):
        self.side = side
        self.auth = auth

    def _keeper(self, state) -> Keep:
        """Identifiers that belong to the logged-in customer stay visible in replies."""
        def keep(p: Pattern, raw: str) -> bool:
            if p.name == "momo_number":
                return owns_number(state, raw)
            if p.name == "ghana_card":
                return owns_card(state, raw)
            if p.name == "kp_txn":
                return owns_txn(state, raw)
            return False
        return keep

    async def run(self, ctx: LayerContext) -> LayerResult:
        state = self.auth.get("shielded", ctx.session_id) if self.auth else None
        text = ctx.text
        notes: list[str] = []
        steps: list[str] = []

        if self.side == "input":
            if state is not None and try_verify(state, text):
                text = text.replace(OTP_CODE, "[OTP]")
                notes.append("Your one-time code was checked by KwikPay and removed before the assistant saw it.")
                steps.append("You are now verified for reversals and PIN resets.")
            hits = find(text)
            if any(p.kind == "credential" for p, _ in hits):
                labels = ", ".join(sorted({p.label for p, _ in hits if p.kind == "credential"}))
                return LayerResult(
                    Decision.BLOCK,
                    f"The message contains a secret ({labels}). Secrets should never be pasted into a chat.",
                    "Remove the key and ask your question again. If it is real, revoke it now.",
                )
            if any(p.kind == "pin" for p, _ in hits):
                notes.append("A PIN was removed before the assistant saw it. KwikPay will never ask for your PIN.")
                steps.append("Never share your PIN, even with KwikPay staff.")
            masked_labels = sorted({p.label for p, _ in hits if p.kind in INPUT_MASK and p.kind != "pin"})
            if masked_labels:
                notes.append(f"Sensitive data ({', '.join(masked_labels)}) was masked before it reached the assistant.")
                steps.append("Avoid sharing personal identifiers in chat.")
            new_text = redact(text, INPUT_MASK)
        else:
            keep = self._keeper(state) if state is not None else None
            hits = [(p, raw) for p, raw in find(text) if p.kind in OUTPUT_MASK and not (keep and keep(p, raw))]
            if not hits:
                return LayerResult()
            labels = ", ".join(sorted({p.label for p, _ in hits}))
            notes.append(f"Sensitive data ({labels}) that is not yours was masked before you saw it.")
            steps.append("Avoid sharing personal identifiers in chat.")
            new_text = redact(text, OUTPUT_MASK, keep)

        if new_text == ctx.text and not notes:
            return LayerResult()
        return LayerResult(Decision.REDACT, " ".join(notes), " ".join(dict.fromkeys(steps)), sanitized_text=new_text)

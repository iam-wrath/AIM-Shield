"""Identity Binding: the Guard sees text, not who is logged in. This layer does.

It knows the session's trust level and owner. On input it looks at the customer's ORIGINAL message
(before any masking) for numbers, Ghana Cards and transaction IDs that are not the owner's:
  * an anonymous customer asking for anything about an account  -> "please verify first"
  * a logged-in customer asking us to act on someone else's data -> blocked
  * someone else's data merely mentioned (a failed-transfer recipient) -> warning, no tool will act on it
`check_tool_call` (kwikpay.authorised) enforces the same rules on every tool call the model makes.
"""
from __future__ import annotations

import re

from ..kwikpay import AuthStore, owns_card, owns_number, owns_txn
from ..models import Decision
from .base import Layer, LayerContext, LayerResult
from .ghana_lens import find

# asking for something to be done to an account (not merely mentioning a PIN)
ACTION = re.compile(r"\b(?:balance|reverse|reversal|refund|reset|send\s+(?:it\s+|am\s+)?back|cancel|unlock)\b", re.I)


class IdentityBinding(Layer):
    name = "identity_binding"
    side = "input"

    def __init__(self, auth: AuthStore):
        self.auth = auth

    async def run(self, ctx: LayerContext) -> LayerResult:
        state = self.auth.get("shielded", ctx.session_id)
        raw = ctx.original_text or ctx.text
        action = bool(ACTION.search(raw))

        foreign: list[str] = []
        for p, value in find(raw):
            if p.name == "momo_number" and not owns_number(state, value):
                foreign.append("a MoMo number")
            elif p.name == "ghana_card" and not owns_card(state, value):
                foreign.append("a Ghana Card number")
            elif p.name == "kp_txn" and not owns_txn(state, value):
                foreign.append("a transaction")
        foreign = list(dict.fromkeys(foreign))

        if state.level == 0 and action:
            return LayerResult(
                Decision.BLOCK,
                "Please verify first: you are not logged in, and account requests need a logged-in, verified customer.",
                "Log in to the KwikPay app, then ask again. We will text you a one-time code.",
            )
        if foreign and action:
            who = state.label if state.owner else "this session"
            return LayerResult(
                Decision.BLOCK,
                f"The request involves someone else's data ({', '.join(foreign)}), not the customer's ({who}). "
                "KwikPay can only act on your own account.",
                "Ask the account holder to contact KwikPay themselves.",
            )
        if foreign:
            return LayerResult(
                Decision.WARN,
                f"The message mentions someone else's data ({', '.join(foreign)}). We will not act on it.",
                "Only your own account and transactions can be changed here.",
            )
        return LayerResult()

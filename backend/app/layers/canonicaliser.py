"""Canonicaliser (W3): undo disguises, then re-check the decoded text with the Guard.

`canonicalise()` is pure and also used by the fail-safe local risk check.
"""
from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from dataclasses import dataclass, field

from ..guard_client import MAX_TEXT_CHARS
from ..models import Decision
from .base import Layer, LayerContext, LayerResult, flag_reason

ZERO_WIDTH = re.compile("[​-‏‪-‮⁠-⁤­﻿]")

# Cyrillic / Greek look-alikes -> Latin
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i",
    "ѕ": "s", "ј": "j", "ԁ": "d", "һ": "h", "ӏ": "l", "ɡ": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "І": "I",
    "α": "a", "ε": "e", "ο": "o", "ν": "v", "ι": "i", "κ": "k", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "Α": "A", "Β": "B", "Ε": "E", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X", "Ζ": "Z",
})

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
                      "@": "a", "$": "s", "!": "i"})
LEET_INSIDE = re.compile(r"[a-z][013457@$!][a-z]")
LEET_LEADING = re.compile(r"^[1347@$][a-z]{3,}")

SPACED = re.compile(r"(?<![^\W_])(?:[^\W_][ .\-_*]){2,}[^\W_](?![^\W_])")
B64 = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/_-])")
HEX = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}){8,}(?![0-9A-Fa-f])")

# Words that make reversed text interesting; used only to decide whether to try reversing.
REVERSE_KEYWORDS = ("ignore", "instruction", "system prompt", "previous", "reveal", "password",
                    "jailbreak", "disregard", "override", "secret", "bypass")


@dataclass
class Canon:
    text: str
    transforms: list[str] = field(default_factory=list)

    @property
    def disguised(self) -> bool:
        """True when something beyond plain Unicode normalisation was undone."""
        return any(t != "unicode-normalised" for t in self.transforms)


def _printable(s: str) -> bool:
    return len(s) >= 6 and sum(c.isprintable() or c in "\n\t" for c in s) / len(s) > 0.95


def _decode_b64(token: str) -> str | None:
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_" if "-" in token or "_" in token else None)
        out = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    return out if _printable(out) and re.search(r"[A-Za-z]{3}", out) else None


def _decode_hex(token: str) -> str | None:
    try:
        out = bytes.fromhex(token).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return out if _printable(out) else None


def _collapse_spaced(m: re.Match) -> str:
    return re.sub(r"[ .\-_*]", "", m.group(0))


def _deleet_token(m: re.Match) -> str:
    tok = m.group(0)
    low = tok.lower()
    if re.search(r"@[\w-]+\.|://", low):  # emails and URLs are not leetspeak
        return tok
    if LEET_INSIDE.search(low) or LEET_LEADING.match(low):
        return low.translate(LEET)
    return tok


def canonicalise(text: str) -> Canon:
    transforms: list[str] = []
    out = unicodedata.normalize("NFKC", text)
    if out != text:
        transforms.append("unicode-normalised")

    stripped = ZERO_WIDTH.sub("", out)
    if stripped != out:
        transforms.append("zero-width characters")
    out = stripped

    mapped = out.translate(HOMOGLYPHS)
    if mapped != out:
        transforms.append("look-alike letters")
    out = mapped

    def b64(m: re.Match) -> str:
        return _decode_b64(m.group(0)) or m.group(0)

    decoded = B64.sub(b64, out)
    if decoded != out:
        transforms.append("base64")
    out = decoded

    def hx(m: re.Match) -> str:
        return _decode_hex(m.group(0)) or m.group(0)

    decoded = HEX.sub(hx, out)
    if decoded != out:
        transforms.append("hex")
    out = decoded

    collapsed = SPACED.sub(_collapse_spaced, out)
    if collapsed != out:
        transforms.append("spaced-out letters")
        collapsed = re.sub(r" {2,}", " ", collapsed)  # word gaps in "i g n o r e   a l l"
    out = collapsed

    deleet = re.sub(r"\S+", _deleet_token, out)
    if deleet != out:
        transforms.append("leetspeak")
    out = deleet

    rev = out[::-1]
    if not any(k in out.lower() for k in REVERSE_KEYWORDS) and any(k in rev.lower() for k in REVERSE_KEYWORDS):
        out = rev
        transforms.append("reversed text")

    return Canon(out, transforms)


class Canonicaliser(Layer):
    name = "canonicaliser"
    side = "input"

    async def run(self, ctx: LayerContext) -> LayerResult:
        canon = canonicalise(ctx.text)
        if canon.text == ctx.text:
            return LayerResult()
        what = ", ".join(canon.transforms)
        decoded = canon.text
        note = ""
        if len(decoded) > MAX_TEXT_CHARS:
            decoded, note = decoded[:MAX_TEXT_CHARS], " (checked the first 4,000 characters)"
        result = await ctx.guard.check_prompt(decoded)
        calls = 0 if result.cached else 1
        if not result.allowed:
            return LayerResult(
                Decision.BLOCK,
                f"The message was disguised ({what}). Once decoded it was flagged: {flag_reason(result)}{note}",
                "Ask your question in plain text.",
                guard_calls=calls,
            )
        if canon.disguised:
            return LayerResult(
                Decision.WARN,
                f"Disguise detected ({what}), but the decoded text looks safe.",
                "Plain text works just as well.",
                guard_calls=calls,
            )
        return LayerResult(guard_calls=calls)

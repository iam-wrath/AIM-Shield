"""Chunker (W5): check long text in overlapping windows instead of truncating or failing.

Used by the pipeline's Guard step (policy.py), not as a Layer: any flagged window flags the whole.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from ..models import GuardResult

WINDOW = 3800
OVERLAP = 200
MAX_WINDOWS = 4  # protects the daily quota; longer text is refused


def chunk_text(text: str, size: int = WINDOW, overlap: int = OVERLAP) -> list[str]:
    if len(text) <= size:
        return [text]
    step = size - overlap
    out = []
    for start in range(0, len(text), step):
        out.append(text[start:start + size])
        if start + size >= len(text):
            break
    return out


def merge_results(results: list[GuardResult]) -> GuardResult:
    """Combine window results: any flag flags the whole; any partial makes it partial."""
    base = results[0].model_copy(deep=True)
    for r in results[1:]:
        for name, chk in r.checks.items():
            cur = base.checks.get(name)
            if cur is None or (chk.flagged and not cur.flagged) or (not chk.ran):
                base.checks[name] = chk
    base.allowed = all(r.allowed for r in results)
    base.flags = sorted({f for r in results for f in r.flags})
    base.status = "partial" if any(r.is_partial for r in results) else "complete"
    base.request_id = "+".join(r.request_id or "?" for r in results)
    base.latency_ms = sum(r.latency_ms or 0 for r in results)
    base.cached = all(r.cached for r in results)
    return base


async def check_windows(
    call: Callable[[str], Awaitable[GuardResult]], windows: list[str]
) -> tuple[GuardResult, int]:
    """Run the Guard on every window concurrently. Returns (merged result, uncached calls)."""
    results = await asyncio.gather(*(call(w) for w in windows))
    return merge_results(list(results)), sum(1 for r in results if not r.cached)

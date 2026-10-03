"""Mini RAG: paragraph chunks from rag_docs/*.md, keyword retrieval, and chunk screening (W6).

Retrieved text is data an attacker may have poisoned, so the shielded path screens every chunk
(Guard /check/prompt plus local injection checks) before it reaches the model.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ..guard_client import MAX_TEXT_CHARS, GuardClient, GuardError
from ..layers.failsafe import local_risk
from ..models import Decision, TraceStep

STOP = set("the a an and or of to in on for is are was be it this that with as at by from what when "
           "where who how do does can i my me you your about tell please all let now part ignore".split())


@dataclass(frozen=True)
class Chunk:
    source: str
    text: str


def _tokens(s: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", s.lower()):
        if w not in STOP and len(w) > 2:
            out.add(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return out


class RagStore:
    def __init__(self, docs_dir: str | Path):
        self.chunks: list[Chunk] = []
        d = Path(docs_dir)
        for f in sorted(d.glob("*.md")) if d.is_dir() else []:
            for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
                para = para.strip()
                if para and not para.startswith("#"):
                    self.chunks.append(Chunk(f.name, para))

    def retrieve(self, query: str, k: int = 3) -> list[Chunk]:
        q = _tokens(query)
        scored = [(len(q & _tokens(c.text)), c) for c in self.chunks]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: -s[0])
        return [c for _, c in scored[:k]]


async def screen_chunks(guard: GuardClient, chunks: list[Chunk]) -> tuple[list[Chunk], TraceStep]:
    """Drop chunks the Guard or local checks flag. Returns (safe chunks, trace step)."""
    t0 = time.perf_counter()

    async def one(c: Chunk) -> tuple[bool, int]:
        risk = local_risk(c.text)
        try:
            r = await guard.check_prompt(c.text[:MAX_TEXT_CHARS])
            return (not r.allowed) or risk.high, 0 if r.cached else 1
        except GuardError:
            return risk.high, 0

    results = await asyncio.gather(*(one(c) for c in chunks)) if chunks else []
    safe = [c for c, (bad, _) in zip(chunks, results) if not bad]
    dropped = [c for c, (bad, _) in zip(chunks, results) if bad]
    calls = sum(n for _, n in results)
    if dropped:
        reason = "Dropped retrieved passage(s) that look like hidden instructions: " + ", ".join(
            sorted({c.source for c in dropped}))
        decision = Decision.WARN
    else:
        reason = f"{len(chunks)} retrieved passage(s) checked" if chunks else "no passages retrieved"
        decision = Decision.ALLOW
    step = TraceStep(layer="rag_screen", decision=decision, reason=reason,
                     latency_ms=round((time.perf_counter() - t0) * 1000, 1), guard_calls=calls)
    return safe, step

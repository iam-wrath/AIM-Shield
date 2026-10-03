#!/usr/bin/env python3
"""Send each probe in probes.json to the Guard (/v1/check/prompt, or /response when the probe
sets "endpoint": "response") and write results.csv.

    python probes/run_probes.py --dry-run          # no network, no token needed
    python probes/run_probes.py --limit 5          # first 5 probes only

Uses a 2.1 s gap between calls (30/min limit). Synthetic data only.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

FIELDS = ["id", "weakness", "allowed", "flags", "status", "confidence",
          "latency_ms", "request_id", "error", "endpoint"]
GAP_SECONDS = 2.1
MAX_CHARS = 4000


def load_probes(path: Path) -> list[dict]:
    probes = json.loads(path.read_text(encoding="utf-8"))
    for p in probes:
        for key in ("id", "weakness", "text"):
            if key not in p:
                raise SystemExit(f"probe {p.get('id', '?')} is missing field '{key}'")
    return probes


def _confidence(checks: dict) -> str:
    for c in checks.values():
        if isinstance(c, dict) and c.get("flagged") and c.get("confidence"):
            return str(c["confidence"])
    return ""


def probe_once(client: httpx.Client, text: str, sleep=time.sleep, endpoint: str = "prompt") -> dict:
    """POST one probe. Returns a CSV row fragment (never raises on HTTP errors)."""
    for attempt in range(2):
        resp = client.post(f"/v1/check/{endpoint}", json={"text": text})
        if resp.status_code == 429 and attempt == 0 and "daily" not in resp.text:
            sleep(float(resp.headers.get("Retry-After", 5)))
            continue
        break
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code} {resp.text[:80].strip()}"}
    d = resp.json()
    return {
        "allowed": d.get("allowed"),
        "flags": "|".join(d.get("flags", [])),
        "status": d.get("status", ""),
        "confidence": _confidence(d.get("checks", {})),
        "latency_ms": d.get("latency_ms", ""),
        "request_id": d.get("request_id", ""),
    }


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--probes", type=Path, default=HERE / "probes.json")
    ap.add_argument("--out", type=Path, default=HERE / "results.csv")
    ap.add_argument("--limit", type=int, default=None, help="only run the first N probes")
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent; no network")
    args = ap.parse_args(argv)

    probes = load_probes(args.probes)
    if args.limit is not None:
        probes = probes[: args.limit]

    if args.dry_run:
        for p in probes:
            note = f"  [{len(p['text'])} chars > {MAX_CHARS}: expect 413]" if len(p["text"]) > MAX_CHARS else ""
            print(f"{p['id']:<10} {p['weakness']:<4} expected={p.get('expected', '?'):<8} "
                  f"{p['text'][:60]!r}{note}")
        print(f"dry run: {len(probes)} probes, ~{len(probes) * GAP_SECONDS:.0f}s, "
              f"{len(probes)} Guard calls (nothing sent)")
        return 0

    own_client = client is None
    if own_client:
        from app.config import ConfigError, get_settings
        try:
            s = get_settings()
        except ConfigError as exc:
            raise SystemExit(str(exc))
        client = httpx.Client(
            base_url=s.guard_url, timeout=s.guard_timeout,
            headers={"Authorization": f"Bearer {s.guard_token.get_secret_value()}",
                     "Content-Type": "application/json"},
        )

    try:
        with args.out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for i, p in enumerate(probes):
                if i:
                    sleep(GAP_SECONDS)
                ep = p.get("endpoint", "prompt")  # "prompt" or "response"
                row = {"id": p["id"], "weakness": p["weakness"], "endpoint": ep,
                       **probe_once(client, p["text"], sleep, ep)}
                w.writerow(row)
                f.flush()
                print(f"{p['id']:<10} allowed={row.get('allowed')} flags={row.get('flags', '')} "
                      f"{row.get('error', '')}")
                if "daily_quota" in row.get("error", ""):
                    print("daily quota exhausted; stopping.")
                    break
    finally:
        if own_client:
            client.close()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

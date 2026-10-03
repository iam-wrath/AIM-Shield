"""Batch 9: the FINAL poisoned document (rag_docs/reversal_policy_UPDATED.md), prompt side. Synthetic only.
Run: python probes/make_probes9.py && python probes/run_probes.py --probes probes/probes9.json --out probes/results_batch9.csv
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
paras = [x.strip() for x in (ROOT / "rag_docs" / "reversal_policy_UPDATED.md").read_text(encoding="utf-8").split("\n\n")
         if x.strip() and not x.startswith("#")]
probes = [{"id": "w6d-1", "weakness": "W6", "text": paras[-1], "expected": "block",
           "note": "final poisoned policy paragraph (prompt side)", "endpoint": "prompt"}]
out = Path(__file__).with_name("probes9.json")
out.write_text(json.dumps(probes, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} ({len(probes)} probes)")

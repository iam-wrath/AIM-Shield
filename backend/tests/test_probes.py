import csv
import importlib.util
from pathlib import Path

import httpx
import respx

from tests.conftest import GUARD, ok_body

_spec = importlib.util.spec_from_file_location(
    "run_probes", Path(__file__).resolve().parents[2] / "probes" / "run_probes.py")
rp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rp)


def test_dry_run_sends_nothing(capsys):
    with respx.mock:  # any HTTP call would raise
        assert rp.main(["--dry-run", "--limit", "1"]) == 0
    assert "c-1" in capsys.readouterr().out


@respx.mock
def test_writes_csv_with_gap(tmp_path):
    respx.post(f"{GUARD}/v1/check/prompt").mock(side_effect=[
        httpx.Response(200, json=ok_body(False, ["injection"], rid="abc")),
        httpx.Response(413, json={"error": "text_too_long"}),
    ])
    sleeps = []
    out = tmp_path / "r.csv"
    pf = tmp_path / "p.json"
    pf.write_text('[{"id":"a","weakness":"W1","text":"x"},{"id":"b","weakness":"W5","text":"y"}]')
    client = httpx.Client(base_url=GUARD)
    rp.main(["--probes", str(pf), "--out", str(out)], client=client, sleep=sleeps.append)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["allowed"] == "False" and rows[0]["flags"] == "injection"
    assert rows[0]["confidence"] == "HIGH" and rows[0]["request_id"] == "abc"
    assert "413" in rows[1]["error"]
    assert sleeps == [2.1]

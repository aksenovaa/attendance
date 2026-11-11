from __future__ import annotations

import csv
from pathlib import Path

from attendance.checks import check1
from attendance.ingest.workly import parse_summary
from attendance.roster import load_roster

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "2026-09"
GOLDEN = Path(__file__).parent / "golden" / "2026-09" / "expected_workly_totals.csv"


def _blocks():
    return (parse_summary(RAW / "09.2026.Офсет.xlsx")
            + parse_summary(RAW / "09.2026.Широкоформат.xlsx"))


def _golden() -> dict[str, dict[str, str]]:
    text = GOLDEN.read_text(encoding="utf-8-sig")   # переживает BOM редактора/Excel
    first = text.splitlines()[0]
    delim = ";" if ";" in first else ","            # переживает замену разделителя
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    return {r["employee"].strip(): r for r in rows}


def test_check1_september():
    roster = load_roster()
    rep = check1(_blocks(), roster, 2026, 9)

    golden = _golden()
    assert {r.employee for r in rep.rows} == set(golden)
    for r in rep.rows:
        g = golden[r.employee]
        assert r.total_hm == g["total_hm"], r.employee
        assert r.diff_min <= r.tolerance_min, (r.employee, r.diff_min)
    assert rep.ok
    assert rep.excluded_present == ["Халбоев Журат"]
    assert rep.not_in_roster == [] and rep.not_in_file == []
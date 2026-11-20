"""Ledger write-back: append и read."""

from __future__ import annotations

from pathlib import Path

from attendance.writeback import LedgerEntry
from attendance.writeback.ledger import append, read


def test_append_and_read(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    entries = [
        LedgerEntry("run1", 1, "2026-11-19T18:00:00", 1, "r2_close", "test", "ts1"),
        LedgerEntry("run1", 2, "2026-11-19T19:00:00", 0, "test", "test", "ts2"),
    ]
    append(entries, ledger)
    read_entries = read(ledger)
    assert len(read_entries) == 2
    assert read_entries[0].employee_id == 1
    assert read_entries[1].employee_id == 2


def test_read_filter_by_run_id(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    entries = [
        LedgerEntry("run1", 1, "t1", 0, "r1", "s1", "ts1"),
        LedgerEntry("run2", 2, "t2", 1, "r2", "s2", "ts2"),
    ]
    append(entries, ledger)
    run1 = read(ledger, run_id="run1")
    assert len(run1) == 1
    assert run1[0].run_id == "run1"

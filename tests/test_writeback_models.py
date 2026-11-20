"""Модели write-back: Insert, InsertPlan, LedgerEntry."""

from __future__ import annotations

from datetime import UTC, datetime

from attendance.writeback import Insert, InsertPlan, LedgerEntry


def test_insert_to_dict() -> None:
    ins = Insert(
        employee_id=123,
        event_time=datetime(2026, 11, 19, 18, 0, 0, tzinfo=UTC),
        code=1,
        reason="r2_close",
        source="writeback:abc123",
    )
    d = ins.to_dict()
    assert d["employee_id"] == 123
    assert d["code"] == 1
    assert "2026-11-19" in d["event_time"]


def test_insert_plan_len() -> None:
    ins = Insert(1, datetime.now(UTC), 0, "test", "test")
    plan = InsertPlan("run1", "2026-11", [ins, ins])
    assert len(plan) == 2
    assert list(plan) == [ins, ins]


def test_ledger_entry_to_dict() -> None:
    entry = LedgerEntry(
        run_id="abc",
        employee_id=123,
        event_time="2026-11-19T18:00:00",
        code=1,
        reason="r2_close",
        source="writeback:abc",
        ts="2026-11-19T14:00:00",
    )
    d = entry.to_dict()
    assert d["run_id"] == "abc"
    assert d["employee_id"] == 123

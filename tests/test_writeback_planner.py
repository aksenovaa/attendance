"""Планировщик write-back: генерация Insert для R2."""

from __future__ import annotations

from pathlib import Path

from attendance.merge import FinalRow
from attendance.store.db import connect
from attendance.writeback.planner import plan


def test_r2_close(tmp_path: Path) -> None:
    """R2: нет ухода → добавить out в 23:59:59."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=480,  # 08:00
            cout=None,  # нет ухода
            worked=None,
            state="",
            tag="",
            source="api",
            pairs=1,
            span=None,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 1
    ins = next(iter(plan_result))
    assert ins.employee_id == 1
    assert ins.code == 1  # out
    assert ins.reason == "r2_close"
    # Проверяем время: 23:59:59
    assert ins.event_time.hour == 23
    assert ins.event_time.minute == 59
    assert ins.event_time.second == 59


def test_no_inserts_for_complete_days(tmp_path: Path) -> None:
    """Полный день (cin + cout) не требует вставок."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=480,
            cout=1200,
            worked=720,
            state="",
            tag="",
            source="api",
            pairs=1,
            span=720,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 0


def test_skip_state_days(tmp_path: Path) -> None:
    """Выходные/отпуска не требуют вставок."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=None,
            cout=None,
            worked=None,
            state="Отпуск",
            tag="",
            source="",
            pairs=0,
            span=None,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 0


def test_orphan_out_open(tmp_path: Path) -> None:
    """Orphan out: есть уход, нет прихода → добавить in в 08:00."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=None,  # нет прихода
            cout=1200,  # 20:00
            worked=None,
            state="",
            tag="",
            source="api",
            pairs=1,
            span=None,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 1
    ins = next(iter(plan_result))
    assert ins.employee_id == 1
    assert ins.code == 0  # in
    assert ins.reason == "orphan_out_open"
    # Проверяем время: 08:00:00
    assert ins.event_time.hour == 8
    assert ins.event_time.minute == 0
    assert ins.event_time.second == 0

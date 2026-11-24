"""Планировщик write-back: генерация Insert для R2."""

from __future__ import annotations

from pathlib import Path

from attendance.merge import FinalRow
from attendance.store.db import connect
from attendance.writeback.planner import plan


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


def test_synth_insert(tmp_path: Path) -> None:
    """Синтез/правка → вставка пары (in, out)."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=480,  # 08:00
            cout=1020,  # 17:00
            worked=540,  # 9 часов
            state="",
            tag="реконструкция",
            source="synth_paper",  # не api
            pairs=1,
            span=540,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 2
    inserts = list(plan_result)
    assert inserts[0].code == 0  # in
    assert inserts[1].code == 1  # out
    assert inserts[0].event_time.hour == 8
    assert inserts[1].event_time.hour == 17


def test_skip_api_source(tmp_path: Path) -> None:
    """Авто-слой (source='api') не вставляется — ждём скан."""
    con = connect(tmp_path / "t.sqlite")
    rows = [
        FinalRow(
            employee_id=1,
            day=15,
            cin=480,
            cout=None,  # R2
            worked=None,
            state="",
            tag="",
            source="api",
            pairs=0,
            span=None,
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
            source="api",
            pairs=0,
            span=None,
        )
    ]
    plan_result = plan(con, "2026-11", rows)
    assert len(plan_result) == 0

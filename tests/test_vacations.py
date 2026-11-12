"""Отпуска: перекрытие событий, приоритет правок, обрезка по месяцу."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from attendance.intake import Correction, save
from attendance.merge import build_final, check3
from attendance.store.db import connect
from attendance.vacations import add, days_by_employee


def _seed(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT INTO employees (employee_id, full_name, shop, exclude_from_timesheet)"
        " VALUES (1, 'Тест', 'offset', 0)"
    )
    for stamp, code in (("2026-11-02 08:00:00", 0), ("2026-11-02 18:00:00", 1)):
        con.execute(
            "INSERT INTO events_raw (event_key, employee_id, event_full_date,"
            " event_code, mode, source, pulled_at, run_id)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"1|{stamp}|{code}", 1, stamp, code, "auto", "api", "", "t"),
        )
    con.commit()


def test_vacation_overrides_events(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    add(con, 1, "2026-11-01", "2026-11-30", "Отпуск", "test")
    rows = build_final(con, "2026-11", "run1")
    by_day = {r.day: r for r in rows}
    assert by_day[2].state == "Отпуск"
    assert by_day[2].worked is None
    assert by_day[2].cin is None
    assert by_day[3].state == "Отпуск"
    assert all(r.ok for r in check3(con, "2026-11", "run1", rows))


def test_correction_wins_over_vacation(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    add(con, 1, "2026-11-01", "2026-11-30", "Отпуск", "test")
    save(
        con,
        "2026-11",
        [Correction(1, 2, "set", "08:00", "20:00", None, "scan:t", "high", "")],
        "scan:t",
    )
    rows = build_final(con, "2026-11", "run2")
    by_day = {r.day: r for r in rows}
    assert by_day[2].state == ""
    assert by_day[2].worked == 720
    assert by_day[3].state == "Отпуск"


def test_month_clipping(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    add(con, 1, "2026-10-25", "2026-11-05", "Отпуск", "test")
    days = days_by_employee(con, "2026-11")[1]
    assert "2026-11-01" in days
    assert "2026-11-05" in days
    assert "2026-11-06" not in days
    assert "2026-10-25" not in days


def test_add_is_idempotent(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    first = add(con, 1, "2026-11-01", "2026-11-30")
    second = add(con, 1, "2026-11-01", "2026-11-30")
    assert first == second

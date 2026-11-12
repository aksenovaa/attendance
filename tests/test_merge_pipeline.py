"""Сквозной проход: события + правка → shifts_final, П3 сходится."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from attendance.intake import Correction, save
from attendance.merge import build_final, check3
from attendance.store.db import connect


def _seed(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT INTO employees (employee_id, full_name, shop, exclude_from_timesheet)"
        " VALUES (1, 'Тест', 'offset', 0)"
    )
    for stamp, code in (("2026-10-01 08:00:00", 0), ("2026-10-01 18:00:00", 1)):
        con.execute(
            "INSERT INTO events_raw (event_key, employee_id, event_full_date,"
            " event_code, mode, source, pulled_at, run_id)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"1|{stamp}|{code}", 1, stamp, code, "auto", "api", "", "t"),
        )
    con.commit()


def test_pipeline(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    save(
        con,
        "2026-10",
        [Correction(1, 2, "add", "08:00", "20:00", None, "manual:t", "high", "")],
        "manual:t",
    )
    rows = build_final(con, "2026-10", "run1")
    by_day = {r.day: r for r in rows}
    assert by_day[1].worked == 600
    assert by_day[2].worked == 720
    assert by_day[2].tag == "добавлено"
    assert by_day[3].state == "Выходной"
    assert all(r.ok for r in check3(con, "2026-10", "run1", rows))

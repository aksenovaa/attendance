"""shifts_final хранит state, числовые минуты и pairs (п.2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from attendance.merge import build_final
from attendance.store.db import connect
from attendance.vacations import add


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


def test_state_and_minutes_persisted(tmp_path: Any) -> None:
    con = connect(Path(tmp_path) / "t.sqlite")
    _seed(con)
    add(con, 1, "2026-11-03", "2026-11-03", "Отпуск", "test")
    build_final(con, "2026-11", "run1")
    rows = {
        r["day"]: r
        for r in con.execute("SELECT * FROM shifts_final WHERE run_id='run1'")
    }
    assert rows["2026-11-02"]["worked_min"] == 600
    assert rows["2026-11-02"]["pairs"] == 1
    assert rows["2026-11-02"]["state"] == ""
    assert rows["2026-11-03"]["state"] == "Отпуск"
    assert rows["2026-11-03"]["worked_min"] is None

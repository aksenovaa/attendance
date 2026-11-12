"""Отпуска как данные: периоды в таблице vacations + автоподстановка в табель.

Приоритет: правки (corrections) > отпуск (vacations) > события API.
Отпуск не начисляет часов: state='Отпуск', времена и отработано очищаются.
Таблица создаётся автоматически при первом обращении (миграция не нужна).
"""

from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS vacations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'Отпуск',
    source TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_vacations_emp ON vacations(employee_id);
CREATE INDEX IF NOT EXISTS idx_vacations_range ON vacations(start_date, end_date);
"""


@dataclass(frozen=True)
class Vacation:
    id: int
    employee_id: int
    start_date: str
    end_date: str
    reason: str
    source: str


def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def month_bounds(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last:02d}"


def add(
    con: sqlite3.Connection,
    employee_id: int,
    start: str,
    end: str,
    reason: str = "Отпуск",
    source: str = "",
) -> int:
    """Идемпотентно: тот же период тому же сотруднику не дублируется."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first:
        raise ValueError(f"end {end} раньше start {start}")
    ensure_schema(con)
    row = con.execute(
        "SELECT id FROM vacations WHERE employee_id=? AND start_date=? AND end_date=?",
        (employee_id, start, end),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = con.execute(
        "INSERT INTO vacations (employee_id, start_date, end_date, reason, source)"
        " VALUES (?,?,?,?,?)",
        (employee_id, start, end, reason, source),
    )
    con.commit()
    return int(cur.lastrowid or 0)


def remove(con: sqlite3.Connection, vacation_id: int) -> int:
    ensure_schema(con)
    cur = con.execute("DELETE FROM vacations WHERE id=?", (vacation_id,))
    con.commit()
    return cur.rowcount


def listing(con: sqlite3.Connection, month: str | None = None) -> list[Vacation]:
    ensure_schema(con)
    query = "SELECT * FROM vacations"
    params: tuple[str, ...] = ()
    if month:
        start, end = month_bounds(month)
        query += " WHERE start_date <= ? AND end_date >= ?"
        params = (end, start)
    query += " ORDER BY employee_id, start_date"
    return [
        Vacation(
            id=int(r["id"]),
            employee_id=int(r["employee_id"]),
            start_date=r["start_date"],
            end_date=r["end_date"],
            reason=r["reason"],
            source=r["source"],
        )
        for r in con.execute(query, params)
    ]


def days_by_employee(con: sqlite3.Connection, month: str) -> dict[int, set[str]]:
    """Дни отпуска внутри месяца: employee_id → множество ISO-дат."""
    ensure_schema(con)
    start, end = month_bounds(month)
    out: dict[int, set[str]] = {}
    query = (
        "SELECT employee_id, start_date, end_date FROM vacations"
        " WHERE start_date <= ? AND end_date >= ?"
    )
    for row in con.execute(query, (end, start)):
        cur = date.fromisoformat(max(row["start_date"], start))
        stop = date.fromisoformat(min(row["end_date"], end))
        bucket = out.setdefault(int(row["employee_id"]), set())
        while cur <= stop:
            bucket.add(cur.isoformat())
            cur += timedelta(days=1)
    return out

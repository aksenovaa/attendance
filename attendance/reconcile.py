"""Сверка каркаса API (t12) с локальным парсером сводных xlsx."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .ingest.workly import parse_summary
from .roster import resolve_name
from .timeutil import hm_to_min, is_hm


@dataclass(frozen=True)
class Diff:
    employee: str
    day: int
    field: str
    api: str
    xlsx: str


def _canon(raw: str | None) -> str:
    return resolve_name(" ".join((raw or "").split()))


def _names(con: sqlite3.Connection) -> dict[int, str]:
    query = (
        "SELECT employee_id, full_name FROM employees WHERE exclude_from_timesheet = 0"
    )
    return {r["employee_id"]: _canon(r["full_name"]) for r in con.execute(query)}


def _api_minutes(
    con: sqlite3.Connection, month: str, names: dict[int, str]
) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    query = "SELECT employee_id, day, work_time FROM day_frame WHERE day LIKE ?"
    for row in con.execute(query, (f"{month}%",)):
        name = names.get(row["employee_id"])
        if name is None:
            continue
        value = row["work_time"] or ""
        minutes = hm_to_min(value) if is_hm(value) else 0
        out[(name, int(row["day"][8:10]))] = minutes
    return out


def _xlsx_minutes(paths: list[Path]) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    for path in paths:
        for block in parse_summary(path):
            name = _canon(block.employee)
            for row in block.rows:
                minutes = 0 if row.dayoff or row.worked is None else row.worked
                out[(name, row.day)] = minutes
    return out


def reconcile(
    con: sqlite3.Connection, month: str, paths: list[Path]
) -> tuple[list[Diff], int]:
    names = _names(con)
    api = _api_minutes(con, month, names)
    xlsx = _xlsx_minutes(paths)
    diffs: list[Diff] = []
    for key in sorted(set(api) | set(xlsx)):
        left, right = api.get(key), xlsx.get(key)
        if left is None:
            diffs.append(Diff(key[0], key[1], "нет в API", "-", str(right)))
        elif right is None:
            diffs.append(Diff(key[0], key[1], "нет в xlsx", str(left), "-"))
        elif left != right:
            diffs.append(Diff(key[0], key[1], "worked", str(left), str(right)))
    return diffs, len(set(api) & set(xlsx))


def write_report(diffs: list[Diff], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Сотрудник", "День", "Поле", "API", "XLSX"])
        for diff in diffs:
            writer.writerow([diff.employee, diff.day, diff.field, diff.api, diff.xlsx])

"""Сверка дней из событий с сводными xlsx (gate S1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .ingest.events import build_days, load_events
from .reconcile import Diff, _names, _xlsx_minutes


def reconcile_events(
    con: sqlite3.Connection, month: str, paths: list[Path]
) -> tuple[list[Diff], int]:
    names = _names(con)
    built = build_days(load_events(con))
    api: dict[tuple[str, int], int] = {}
    for (emp, date), item in built.items():
        if not date.startswith(month):
            continue
        name = names.get(emp)
        if name is None:
            continue
        api[(name, int(date[8:10]))] = item.worked or 0

    xlsx = _xlsx_minutes(paths)
    diffs: list[Diff] = []
    for key in sorted(set(api) | set(xlsx)):
        left, right = api.get(key, 0), xlsx.get(key, 0)
        if left == right:
            continue
        field = "worked"
        if key not in api:
            field = "нет событий"
        elif key not in xlsx:
            field = "нет в xlsx"
        diffs.append(Diff(key[0], key[1], field, str(left), str(right)))
    return diffs, len(set(api) & set(xlsx))

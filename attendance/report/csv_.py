"""Итоговый табель CSV: «;», DD.MM.YYYY, блоки по сотрудникам, строка «Итого»."""

from __future__ import annotations

import calendar
import csv
from datetime import date
from pathlib import Path

from ..merge import FinalRow
from ..timeutil import min_to_hm

WEEKDAYS = ("пон", "втор", "сред", "чет", "пят", "суб", "вос")
HEADER = [
    "Сотрудник / Итого",
    "Дата",
    "Неделя",
    "Приход",
    "Уход",
    "Отработано",
    "Метка",
]


def write(
    path: Path,
    month: str,
    rows: list[FinalRow],
    names: dict[int, str],
    order: list[int] | None = None,
) -> Path:
    year, mon = (int(x) for x in month.split("-"))
    ndays = calendar.monthrange(year, mon)[1]
    by_emp: dict[int, dict[int, FinalRow]] = {}
    for row in rows:
        by_emp.setdefault(row.employee_id, {})[row.day] = row
    sequence = order or sorted(by_emp)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(HEADER)
        for eid in sequence:
            days = by_emp.get(eid, {})
            name = names.get(eid, str(eid))
            writer.writerow([name, "", "", "", "", "", ""])
            total = 0
            for day in range(1, ndays + 1):
                d = date(year, mon, day)
                row = days.get(day)
                stamp = d.strftime("%d.%m.%Y")
                week = WEEKDAYS[d.weekday()]
                if row is None or row.state:
                    state = row.state if row else "Выходной"
                    writer.writerow(["", stamp, week, state, "", "", state])
                    continue
                total += row.worked or 0
                writer.writerow(
                    [
                        "",
                        stamp,
                        week,
                        min_to_hm(row.cin) if row.cin is not None else "",
                        min_to_hm(row.cout) if row.cout is not None else "",
                        min_to_hm(row.worked) if row.worked is not None else "",
                        row.tag,
                    ]
                )
            writer.writerow(["Итого", "", "", "", "", min_to_hm(total), ""])
    return path

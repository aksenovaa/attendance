"""П5: формальная валидация утверждённого табеля.

Шапка, метки из списка, времена HH:MM, даты DD.MM.YYYY, недели,
строки Итого, отсутствие дублей (сотрудник, день), состояние == метка.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

HEADER = [
    "Сотрудник / Итого",
    "Дата",
    "Неделя",
    "Приход",
    "Уход",
    "Отработано",
    "Метка",
]
ALLOWED_TAGS = {"", "добавлено", "правка", "реконструкция"}
ALLOWED_STATES = {"Выходной", "Отпуск"}
WEEKDAYS = {"пон", "втор", "сред", "чет", "пят", "суб", "вос"}
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def check5(path: Path) -> list[str]:
    """Список нарушений формата. Пустой список = формат корректен."""
    issues: list[str] = []
    seen: set[tuple[str, str]] = set()
    emps_with_days: set[str] = set()
    emps_with_total: set[str] = set()

    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter=";"))

    if not rows:
        return ["файл пуст"]
    if rows[0] != HEADER:
        issues.append(f"строка 1: шапка не совпадает с {HEADER}")

    current: str | None = None
    for lineno, row in enumerate(rows[1:], start=2):
        if len(row) < 7:
            issues.append(f"строка {lineno}: меньше 7 колонок")
            continue
        col0, date, week, cin, cout, worked, tag = (c.strip() for c in row[:7])

        if col0 and not col0.startswith("Итого") and not date:
            current = col0
            continue

        if col0.startswith("Итого"):
            if current is None:
                issues.append(f"строка {lineno}: Итого вне блока сотрудника")
            elif not TIME_RE.match(worked):
                issues.append(f"строка {lineno}: итог {worked!r} не ЧЧ:ММ")
            else:
                emps_with_total.add(current)
            continue

        if not current:
            issues.append(f"строка {lineno}: день вне блока сотрудника")
            continue
        if not DATE_RE.match(date):
            issues.append(f"строка {lineno}: дата {date!r} не DD.MM.YYYY")
            continue
        if week not in WEEKDAYS:
            issues.append(f"строка {lineno}: неделя {week!r} не из списка")
        if (current, date) in seen:
            issues.append(f"строка {lineno}: дубль ({current}, {date})")
        seen.add((current, date))
        emps_with_days.add(current)

        if cin in ALLOWED_STATES:
            if cin != tag:
                issues.append(f"строка {lineno}: состояние {cin!r} != метка {tag!r}")
            if cout or worked:
                issues.append(
                    f"строка {lineno}: у состояния {cin!r} заполнены уход/отработано"
                )
            continue

        if tag not in ALLOWED_TAGS:
            issues.append(f"строка {lineno}: метка {tag!r} не из списка")
        for label, val in (("приход", cin), ("уход", cout), ("отработано", worked)):
            if val and not TIME_RE.match(val):
                issues.append(f"строка {lineno}: {label} {val!r} не HH:MM")
        if (cin or cout or worked) and not (cin and cout and worked):
            issues.append(f"строка {lineno}: неполная строка приход/уход/отработано")

    for emp in emps_with_days - emps_with_total:
        issues.append(f"{emp}: нет строки Итого")
    return issues

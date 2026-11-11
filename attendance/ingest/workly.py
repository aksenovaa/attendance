"""Парсер сводных таблиц Workly (MM.YYYY.Офсет.xlsx / .Широкоформат.xlsx).

Шапка сотрудника — merged A:E (значение только в A); таблица имеет
двухстрочную шапку («Дата|Факт» + «Приход|Уход|Отработано»).
"""

from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from ..models import DAYOFF, ShiftRow, WorklyBlock
from ..roster import resolve_name
from ..timeutil import hm_to_min, is_hm

_DATE_RE = re.compile(r"(\d{1,2})\s+[а-яёА-ЯЁ]+\s+\d{4}")
_SKIP_A = {"Дата", "Ф.И.О", ""}
_SKIP_B = {"Приход", "Уход", "Факт", "Должность"}
_JUNK = ("PHPExcel", "Worksheet", "Document", "Табель", "График")


def _s(value: object) -> str:
    return "" if value is None else str(value).strip()


def _opt_min(value: object) -> int | None:
    text = _s(value)
    return hm_to_min(text) if is_hm(text) else None


def _is_junk(text: str, sheet_title: str | None) -> bool:
    if sheet_title and sheet_title in text:
        return True
    return any(marker in text for marker in _JUNK)


def parse_summary(path: Path) -> list[WorklyBlock]:
    book = load_workbook(path, data_only=True)
    sheet = book.active
    if sheet is None:
        return []

    blocks: list[WorklyBlock] = []
    emp: str | None = None
    rows: list[ShiftRow] = []

    def flush(total: int) -> None:
        nonlocal emp, rows
        if emp is not None:
            blocks.append(WorklyBlock(emp, tuple(rows), total))
        emp, rows = None, []

    for row in sheet.iter_rows(values_only=True):
        first = _s(row[0]) if len(row) > 0 else ""
        second = _s(row[1]) if len(row) > 1 else ""
        tail = [_s(cell) for cell in row[3:7]]

        if not first and any(is_hm(item) for item in tail):
            flush(hm_to_min(next(item for item in tail if is_hm(item))))
            continue

        match = _DATE_RE.search(first)
        if match:
            if emp is None:
                raise ValueError(f"Строка дня без сотрудника: {row}")
            day = int(match.group(1))
            if second == DAYOFF:
                rows.append(ShiftRow(emp, day, None, None, None, dayoff=True))
            else:
                cout = _opt_min(row[2]) if len(row) > 2 else None
                worked = _opt_min(row[3]) if len(row) > 3 else None
                rows.append(ShiftRow(emp, day, _opt_min(second), cout, worked))
            continue

        if first in _SKIP_A or second in _SKIP_B:
            continue

        if first and second in ("", first) and not _is_junk(first, sheet.title):
            flush(0)
            emp = resolve_name(first)

    return blocks

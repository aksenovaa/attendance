"""Парсер сводных таблиц Workly (файлы MM.YYYY.Офсет.xlsx / .Широкоформат.xlsx).

Структура листа: блок сотрудника = строка-заголовок (merged A:E, значение только в A),
строки «дата | приход | уход | отработано», строка итога (HH:MM в дальнем столбце).
Важно: openpyxl отдаёт None в не-якорных ячейках merged-диапазонов.
"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from ..models import DAYOFF, ShiftRow, WorklyBlock
from ..timeutil import hm_to_min, is_hm

_DATE_RE = re.compile(r"(\d{1,2})\s+[а-яёА-ЯЁ]+\s+\d{4}")   # \s ловит и \xa0 перед «г.»
_SKIP_A = {"Дата", "Ф.И.О", ""}
_SKIP_B = {"Приход", "Уход", "Факт", "Должность"}
_JUNK = ("PHPExcel", "Worksheet", "Document", "Табель", "График")


def _s(v: object) -> str:
    return "" if v is None else str(v).strip()


def _opt_min(v: object) -> int | None:
    s = _s(v)
    return hm_to_min(s) if is_hm(s) else None


def _is_junk(a: str, sheet_title: str | None) -> bool:
    """Титульные строки экспорта не должны становиться «сотрудниками»."""
    if sheet_title and sheet_title in a:
        return True
    return any(k in a for k in _JUNK)


def parse_summary(path: Path) -> list[WorklyBlock]:
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    if ws is None:
        return []

    blocks: list[WorklyBlock] = []
    emp: str | None = None
    rows: list[ShiftRow] = []

    def flush(total: int) -> None:
        nonlocal emp, rows
        if emp is not None:
            blocks.append(WorklyBlock(emp, tuple(rows), total))
        emp, rows = None, []

    for row in ws.iter_rows(values_only=True):
        a = _s(row[0]) if len(row) > 0 else ""
        b = _s(row[1]) if len(row) > 1 else ""
        tail = [_s(c) for c in row[3:7]] if len(row) >= 7 else [_s(c) for c in row[3:]]

        if not a and any(is_hm(t) for t in tail):            # строка итога блока
            flush(hm_to_min(next(t for t in tail if is_hm(t))))
            continue

        m = _DATE_RE.search(a)
        if m:                                                # строка дня
            assert emp is not None, f"Строка дня без сотрудника: {row}"
            day = int(m.group(1))
            if b == DAYOFF:
                rows.append(ShiftRow(emp, day, None, None, None, dayoff=True))
            else:
                cout = _opt_min(row[2]) if len(row) > 2 else None
                worked = _opt_min(row[3]) if len(row) > 3 else None
                rows.append(ShiftRow(emp, day, _opt_min(b), cout, worked))
            continue

        if a in _SKIP_A or b in _SKIP_B:                     # шапки таблиц/пустые
            continue

        if a and b in ("", a) and not _is_junk(a, ws.title):  # шапка сотрудника (merged A:E)
            flush(0)
            emp = a
            continue

    return blocks
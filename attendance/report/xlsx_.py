"""Генератор XLSX: утверждённый формат табеля."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.pagebreak import Break

from ..merge import FinalRow
from ..timeutil import min_to_hm
from .csv_ import HEADER, WEEKDAYS


def write_xlsx(
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

    wb = Workbook()
    ws = wb.active
    ws.title = month

    header_font = Font(bold=True)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center")

    for col, title in enumerate(HEADER, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font = header_font
        cell.border = border
        cell.alignment = center

    # Скрываем колонку G (Метка) — она для сверки, не для печати
    ws.column_dimensions["G"].hidden = True

    # Сквозная шапка (повторять строку 1 на каждой странице при печати)
    ws.print_title_rows = "1:1"

    r = 2
    for eid in sequence:
        days = by_emp.get(eid, {})
        name = names.get(eid, str(eid))
        cell = ws.cell(row=r, column=1, value=name)
        cell.font = header_font
        for col in range(1, 8):
            ws.cell(row=r, column=col).border = border
        r += 1

        total = 0
        for day in range(1, ndays + 1):
            d = date(year, mon, day)
            row = days.get(day)
            stamp = d.strftime("%d.%m.%Y")
            week = WEEKDAYS[d.weekday()]
            if row is None or row.state:
                state = row.state if row else "Выходной"
                values = ["", stamp, week, state, "", "", state]
            else:
                total += row.worked or 0
                values = [
                    "",
                    stamp,
                    week,
                    min_to_hm(row.cin) if row.cin is not None else "",
                    min_to_hm(row.cout) if row.cout is not None else "",
                    min_to_hm(row.worked) if row.worked is not None else "",
                    row.tag,
                ]
            for col, value in enumerate(values, start=1):
                cell = ws.cell(row=r, column=col, value=value)
                cell.border = border
                if col > 1:
                    cell.alignment = center
            r += 1

        # Итого
        ws.cell(row=r, column=1, value="Итого")
        total_cell = ws.cell(row=r, column=6, value=min_to_hm(total))
        total_cell.font = header_font
        for col in range(1, 8):
            ws.cell(row=r, column=col).border = border
        r += 1

        # Разрыв страницы ПОСЛЕ строки Итого (перед следующим ФИО)
        ws.row_breaks.append(Break(id=r - 1))

    for i, width in enumerate((22, 12, 8, 8, 8, 12, 16), start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    wb.save(path)
    return path

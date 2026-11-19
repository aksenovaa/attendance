"""Генератор PDF: утверждённый формат табеля (шрифт с кириллицей обязателен)."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..merge import FinalRow
from ..timeutil import min_to_hm
from .csv_ import WEEKDAYS

_FONT_CANDIDATES = [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
]


def _register_font() -> tuple[str, str]:
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("Cyr", regular))
            pdfmetrics.registerFont(TTFont("Cyr-Bold", bold))
            return "Cyr", "Cyr-Bold"
    raise FileNotFoundError(
        "Шрифт с поддержкой кириллицы не найден. "
        "Установите: sudo apt-get install -y fonts-dejavu-core"
    )


def write_pdf(
    path: Path,
    month: str,
    rows: list[FinalRow],
    names: dict[int, str],
    order: list[int] | None = None,
) -> Path:
    font, font_bold = _register_font()
    year, mon = (int(x) for x in month.split("-"))
    ndays = calendar.monthrange(year, mon)[1]
    by_emp: dict[int, dict[int, FinalRow]] = {}
    for row in rows:
        by_emp.setdefault(row.employee_id, {})[row.day] = row
    sequence = order or sorted(by_emp)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    story = []
    title_style = ParagraphStyle("Title", fontName=font_bold, fontSize=14, spaceAfter=8)
    story.append(Paragraph(f"Табель за {month}", title_style))
    story.append(Spacer(1, 4 * mm))

    # Заголовок без колонки "Метка" (6 колонок вместо 7)
    header = ["Сотрудник / Итого", "Дата", "Неделя", "Приход", "Уход", "Отработано"]
    col_widths = [55 * mm, 22 * mm, 14 * mm, 18 * mm, 18 * mm, 22 * mm]

    from reportlab.platypus import PageBreak

    for eid in sequence:
        days = by_emp.get(eid, {})
        name = names.get(eid, str(eid))
        data: list[list[str]] = [list(header)]
        data.append([name, "", "", "", "", ""])
        total = 0
        for day in range(1, ndays + 1):
            d = date(year, mon, day)
            row = days.get(day)
            stamp = d.strftime("%d.%m.%Y")
            week = WEEKDAYS[d.weekday()]
            if row is None or row.state:
                state = row.state if row else "Выходной"
                data.append(["", stamp, week, state, "", ""])
            else:
                total += row.worked or 0
                data.append(
                    [
                        "",
                        stamp,
                        week,
                        min_to_hm(row.cin) if row.cin is not None else "",
                        min_to_hm(row.cout) if row.cout is not None else "",
                        min_to_hm(row.worked) if row.worked is not None else "",
                    ]
                )
        data.append(["Итого", "", "", "", "", min_to_hm(total)])

        table = Table(data, colWidths=col_widths, repeatRows=1)
        style: list[tuple] = [
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, 1), font_bold),  # строка с ФИО
            ("FONTNAME", (0, len(data) - 1), (-1, len(data) - 1), font_bold),  # Итого
        ]
        table.setStyle(TableStyle(style))
        story.append(table)
        story.append(PageBreak())

    # Убираем последний PageBreak (чтобы не было пустой страницы в конце)
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    return path

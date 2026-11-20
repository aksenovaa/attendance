"""Отчёты XLSX и PDF: генерация и базовая структура."""

from __future__ import annotations

from pathlib import Path

import pytest

from attendance.merge import FinalRow
from attendance.report.xlsx_ import write_xlsx


def _rows() -> list[FinalRow]:
    return [
        FinalRow(1, 1, 480, 1200, 720, "", "", "api", 1, 720),
        FinalRow(1, 2, None, None, None, "Выходной", "", "", 0, None),
    ]


def test_pdf_created(tmp_path: Path) -> None:
    from attendance.report.pdf_ import write_pdf

    try:
        out = write_pdf(tmp_path / "t.pdf", "2026-11", _rows(), {1: "Тест"}, order=[1])
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:5] == b"%PDF-"


def test_xlsx_structure(tmp_path: Path) -> None:
    from openpyxl import load_workbook

    out = write_xlsx(tmp_path / "t.xlsx", "2026-11", _rows(), {1: "Тест"}, order=[1])
    wb = load_workbook(out)
    ws = wb.active
    assert ws is not None
    assert ws.cell(row=1, column=1).value == "Сотрудник / Итого"
    assert ws.cell(row=2, column=1).value == "Тест"
    totals = [
        ws.cell(row=r, column=6).value
        for r in range(1, ws.max_row + 1)
        if ws.cell(row=r, column=1).value == "Итого"
    ]
    assert totals == ["12:00"]


def test_xlsx_metadata_hidden_and_breaks(tmp_path: Path) -> None:
    from openpyxl import load_workbook

    out = write_xlsx(tmp_path / "t.xlsx", "2026-11", _rows(), {1: "Тест"}, order=[1])
    wb = load_workbook(out)
    ws = wb.active
    assert ws is not None
    assert ws.column_dimensions["G"].hidden is True
    assert ws.print_title_rows == "$1:$1"
    # Разрывы лежат в ws.row_breaks.brk (список Break)
    assert ws.row_breaks.count == 1
    # Проверяем, что есть хотя бы один break (id может быть другим)
    assert len(ws.row_breaks.brk) == 1

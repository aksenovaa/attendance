"""П4: арифметика и дубли."""

from __future__ import annotations

from attendance.checks_final import check4, duplicates
from attendance.models import ShiftRow
from attendance.timeutil import hm_to_min


def _row(day: int, worked: str) -> ShiftRow:
    return ShiftRow(
        "Тест", day, hm_to_min("08:00"), hm_to_min("20:00"), hm_to_min(worked)
    )


def test_check4_flags_bad_row() -> None:
    assert [r.ok for r in check4([_row(1, "12:00"), _row(2, "11:00")])] == [True, False]


def test_duplicates_detected() -> None:
    assert duplicates([_row(1, "12:00"), _row(1, "12:00")]) == [("Тест", 1)]

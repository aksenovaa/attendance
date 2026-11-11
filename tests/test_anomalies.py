"""Детекторы: реальные кейсы сентября/октября + простые числовые кейсы."""

from __future__ import annotations

from attendance.models import ShiftRow
from attendance.rules.anomalies import Code, detect
from attendance.timeutil import hm_to_min


def _row(
    cin: str | None, cout: str | None, worked: str | None, day: int = 1
) -> ShiftRow:
    return ShiftRow(
        employee="Тест",
        day=day,
        cin=hm_to_min(cin) if cin else None,
        cout=hm_to_min(cout) if cout else None,
        worked=hm_to_min(worked) if worked else None,
    )


def _codes(row: ShiftRow, shop: str = "offset") -> set[Code]:
    return {f.code for f in detect(row, shop)}


def test_zero_shift_is_r4() -> None:
    assert Code.R4_ZERO in _codes(_row("07:35", "07:35", "00:00"))


def test_glitch_pair_is_r1() -> None:
    assert Code.R1_GLITCH in _codes(_row("20:19", "20:20", "00:00"))


def test_shifted_out_is_r3() -> None:
    assert Code.R3_SHIFTED in _codes(_row("07:33", "07:57", "24:23"))


def test_missing_out_is_r2() -> None:
    assert Code.R2_NO_OUT in _codes(_row("09:01", None, None))


def test_recalc_proposes_duration() -> None:
    hits = [
        f
        for f in detect(_row("08:00", "20:00", "03:00"), "offset")
        if f.code is Code.R1_RECALC
    ]
    assert hits
    assert hits[0].worked == hm_to_min("12:00")


def test_midnight_crossing_and_long_shift() -> None:
    codes = _codes(_row("07:00", "01:00", "18:00"), "wide")
    assert Code.R5_NIGHT in codes
    assert Code.R6_LONG in codes
    assert Code.R9_MIDNIGHT not in codes


def test_dayoff_has_no_findings() -> None:
    assert detect(ShiftRow("Тест", 1, None, None, None, dayoff=True), "offset") == []

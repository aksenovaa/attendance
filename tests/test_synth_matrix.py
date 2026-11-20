"""Синтез по матрице: часы по дням → пары (приход, уход)."""

from __future__ import annotations

from attendance.synth_matrix import MatrixDay, build_corrections


def test_simple_day() -> None:
    corrs = build_corrections(1, "2026-11", [MatrixDay(2, 9 * 60)])
    assert len(corrs) == 1
    c = corrs[0]
    assert c.cin == "08:00"
    assert c.cout == "17:00"
    assert c.worked == "09:00"
    assert c.source == "synth_paper"


def test_cross_midnight() -> None:
    corrs = build_corrections(1, "2026-11", [MatrixDay(3, 16 * 60 + 33)])
    c = corrs[0]
    assert c.cin == "08:00"
    assert c.cout == "00:33"  # переход через полночь
    assert c.worked == "16:33"


def test_skip_zero_hours() -> None:
    corrs = build_corrections(1, "2026-11", [MatrixDay(4, 0), MatrixDay(5, 8 * 60)])
    assert len(corrs) == 1
    assert corrs[0].day == 5

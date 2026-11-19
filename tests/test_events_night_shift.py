"""Ночная смена (переход через полночь): span считается по полным timestamp."""

from __future__ import annotations

from datetime import datetime

from attendance.ingest.events import Event, build_days


def _ev(ts: str, code: int) -> Event:
    return Event(1, datetime.fromisoformat(ts), code, "auto")


def test_night_shift_span() -> None:
    """Смена 07:39 → 00:12 следующего дня: span = 992 мин (16:32), усечение секунд."""
    events = [
        _ev("2026-11-10 07:39:33", 0),  # in
        _ev("2026-11-11 00:12:25", 1),  # out
    ]
    built = build_days(events)
    b = built[(1, "2026-11-10")]
    assert b.worked == 992  # 16:32 (усечение секунд)
    assert b.span == 992  # 16:32 (полные timestamp, усечение)
    assert b.pairs == 1

"""Модель пар: простые кейсы + реальный день Альфредо 14.09."""

from __future__ import annotations

from datetime import datetime

from attendance.ingest.events import Event, build_days


def _ev(ts: str, code: int, emp: int = 1) -> Event:
    return Event(emp, datetime.fromisoformat(ts), code, "auto")


def test_real_day_alfredo_1409() -> None:
    built = build_days([_ev("2026-09-14 07:46:40", 0), _ev("2026-09-14 19:52:33", 1)])
    day = built[(1, "2026-09-14")]
    assert day.worked == 725
    assert day.pairs == 1


def test_cross_midnight_belongs_to_in_date() -> None:
    built = build_days([_ev("2026-09-01 20:00:00", 0), _ev("2026-09-02 02:00:00", 1)])
    assert built[(1, "2026-09-01")].worked == 360
    assert (1, "2026-09-02") not in built


def test_shifted_out_and_new_in() -> None:
    built = build_days(
        [
            _ev("2026-09-01 08:00:00", 0),
            _ev("2026-09-02 07:00:00", 1),
            _ev("2026-09-02 07:05:00", 0),
        ]
    )
    assert built[(1, "2026-09-01")].worked == 23 * 60
    assert built[(1, "2026-09-02")].unclosed_in is True


def test_two_pairs_are_summed() -> None:
    built = build_days(
        [
            _ev("2026-09-01 08:00:00", 0),
            _ev("2026-09-01 12:00:00", 1),
            _ev("2026-09-01 13:00:00", 0),
            _ev("2026-09-01 18:00:00", 1),
        ]
    )
    day = built[(1, "2026-09-01")]
    assert day.pairs == 2
    assert day.worked == 9 * 60


def test_orphan_out_is_flagged() -> None:
    built = build_days([_ev("2026-09-01 07:00:00", 1)])
    assert built[(1, "2026-09-01")].orphan_out == 1
    assert built[(1, "2026-09-01")].worked is None


def test_pair_over_limit_is_not_paired() -> None:
    built = build_days([_ev("2026-10-23 08:17:00", 0), _ev("2026-10-24 23:31:00", 1)])
    assert built[(1, "2026-10-23")].worked is None
    assert built[(1, "2026-10-23")].unclosed_in is True
    assert built[(1, "2026-10-24")].orphan_out == 1

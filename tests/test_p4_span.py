"""П4: секунды не дают ложных FAIL; мультипара с ночью проходит по span."""

from __future__ import annotations

from datetime import datetime

from attendance.checks_p4 import check4_rows
from attendance.ingest.events import Event, build_days
from attendance.merge import FinalRow


def _ev(ts: str, code: int) -> Event:
    return Event(1, datetime.fromisoformat(ts), code, "auto")


def test_seconds_do_not_break_p4() -> None:
    built = build_days([_ev("2026-11-04 08:51:30", 0), _ev("2026-11-04 23:12:10", 1)])
    b = built[(1, "2026-11-04")]
    row = FinalRow(1, 4, b.cin, b.cout, b.worked, "", "", "api", b.pairs, b.span)
    assert check4_rows([row]) == []


def test_multipair_across_midnight() -> None:
    built = build_days(
        [
            _ev("2026-11-10 00:11:55", 0),
            _ev("2026-11-10 00:12:07", 1),
            _ev("2026-11-10 07:39:33", 0),
            _ev("2026-11-11 00:12:25", 1),
        ]
    )
    b = built[(1, "2026-11-10")]
    row = FinalRow(1, 10, b.cin, b.cout, b.worked, "", "", "api", b.pairs, b.span)
    assert b.pairs == 2
    assert check4_rows([row]) == []

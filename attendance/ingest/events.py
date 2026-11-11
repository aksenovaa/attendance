"""Построение дней из сырых событий Workly по модели пар in→out.

Смена относится к дате ПРИХОДА. Сироты (out без in, in без out) помечаются,
но не достраиваются — это работа правил R1–R9 и правок.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Mode = Literal["pairs", "span"]


@dataclass(frozen=True)
class Event:
    employee_id: int
    ts: datetime
    code: int  # 0 = in, 1 = out
    mode: str  # auto | manual


@dataclass(frozen=True)
class Built:
    cin: int | None
    cout: int | None
    worked: int | None
    pairs: int
    orphan_out: int
    unclosed_in: bool


@dataclass
class _Acc:
    cin: int | None = None
    cout: int | None = None
    seconds: int = 0
    pairs: int = 0
    orphan_out: int = 0
    unclosed_in: bool = False
    first_in: datetime | None = None
    last_out: datetime | None = None


def _minutes(ts: datetime) -> int:
    return ts.hour * 60 + ts.minute


def _key(emp: int, ts: datetime) -> tuple[int, str]:
    return emp, ts.date().isoformat()


def load_events(con: sqlite3.Connection) -> list[Event]:
    """Все события из БД: границы месяцев берём с запасом, фильтруем позже."""
    query = (
        "SELECT employee_id, event_full_date, event_code, mode FROM events_raw "
        "ORDER BY employee_id, event_full_date"
    )
    return [
        Event(
            row["employee_id"],
            datetime.fromisoformat(row["event_full_date"]),
            row["event_code"],
            row["mode"] or "",
        )
        for row in con.execute(query)
    ]


def build_days(
    events: Iterable[Event], mode: Mode = "pairs"
) -> dict[tuple[int, str], Built]:
    by_emp: dict[int, list[Event]] = defaultdict(list)
    for event in events:
        by_emp[event.employee_id].append(event)

    acc: dict[tuple[int, str], _Acc] = {}
    for emp, items in by_emp.items():
        items.sort(key=lambda e: e.ts)
        open_in: datetime | None = None
        for event in items:
            if event.code == 0:
                if open_in is not None:
                    acc[_key(emp, open_in)].unclosed_in = True
                open_in = event.ts
                slot = acc.setdefault(_key(emp, event.ts), _Acc())
                if slot.cin is None:
                    slot.cin = _minutes(event.ts)
                    slot.first_in = event.ts
                continue
            if open_in is None:
                acc.setdefault(_key(emp, event.ts), _Acc()).orphan_out += 1
                continue
            start = open_in
            open_in = None
            slot = acc.setdefault(_key(emp, start), _Acc())
            slot.pairs += 1
            slot.seconds += int((event.ts - start).total_seconds())
            slot.cout = _minutes(event.ts)
            slot.last_out = event.ts
            if slot.cin is None:
                slot.cin = _minutes(start)
                slot.first_in = start
        if open_in is not None:
            acc[_key(emp, open_in)].unclosed_in = True

    result: dict[tuple[int, str], Built] = {}
    for key, slot in acc.items():
        seconds = slot.seconds
        if mode == "span" and slot.first_in and slot.last_out:
            seconds = int((slot.last_out - slot.first_in).total_seconds())
        worked = seconds // 60 if slot.pairs else None
        result[key] = Built(
            cin=slot.cin,
            cout=slot.cout,
            worked=worked,
            pairs=slot.pairs,
            orphan_out=slot.orphan_out,
            unclosed_in=slot.unclosed_in,
        )
    return result

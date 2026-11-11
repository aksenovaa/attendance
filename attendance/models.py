"""Доменные модели. Время внутри — int минут от полуночи."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Minute = int
Second = int
DAYOFF = "Выходной"


class Dept(str, Enum):
    OFFSET = "offset"
    WIDE = "wide"


class EventKind(str, Enum):
    IN = "in"
    OUT = "out"


@dataclass(frozen=True)
class Employee:
    name: str
    dept: Dept
    aliases: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    exclude_reports: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawEvent:
    date: str
    employee: str
    kind: EventKind
    sec: Second
    raw: str


@dataclass(frozen=True)
class ShiftRow:
    employee: str
    day: int
    cin: Minute | None
    cout: Minute | None
    worked: Minute | None
    dayoff: bool = False
    source: str = "workly"


@dataclass(frozen=True)
class WorklyBlock:
    employee: str
    rows: tuple[ShiftRow, ...]
    total: Minute

    def sum_worked(self) -> Minute:
        return sum(r.worked for r in self.rows if r.worked is not None)

    def worked_rows(self) -> int:
        return sum(1 for r in self.rows if r.worked is not None)

    def days_present(self) -> set[int]:
        return {r.day for r in self.rows}
"""Проверка П4: арифметика строк и отсутствие дублей (сотрудник, день)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import ShiftRow
from .timeutil import duration_min


@dataclass(frozen=True)
class RowCheck:
    employee: str
    day: int
    worked: int
    expected: int
    pairs: int = 1

    @property
    def ok(self) -> bool:
        if self.pairs <= 1:
            return self.worked == self.expected
        return 0 <= self.worked <= self.expected


def check4(
    rows: Iterable[ShiftRow],
    pairs: dict[tuple[str, int], int] | None = None,
) -> list[RowCheck]:
    pairs = pairs or {}
    out: list[RowCheck] = []
    for row in rows:
        if row.dayoff or row.cin is None or row.cout is None or row.worked is None:
            continue
        out.append(
            RowCheck(
                row.employee,
                row.day,
                row.worked,
                duration_min(row.cin, row.cout),
                pairs.get((row.employee, row.day), 1),
            )
        )
    return out


def duplicates(rows: Iterable[ShiftRow]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    dup: list[tuple[str, int]] = []
    for row in rows:
        key = (row.employee, row.day)
        if key in seen:
            dup.append(key)
        seen.add(key)
    return dup

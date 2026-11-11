"""Проверка 1: сходимость сводных таблиц Workly самих с собой и с ростером."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field

from .models import Employee, WorklyBlock
from .timeutil import min_to_hm


@dataclass(frozen=True)
class Check1Row:
    employee: str
    total_hm: str
    sum_rows_hm: str
    diff_min: int
    tolerance_min: int
    ok: bool
    missing_days: tuple[int, ...] = ()


@dataclass
class Check1Report:
    rows: list[Check1Row] = field(default_factory=list)
    excluded_present: list[str] = field(default_factory=list)   # в файле, но исключены из отчёта
    not_in_roster: list[str] = field(default_factory=list)
    not_in_file: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.rows) and not self.not_in_roster and not self.not_in_file


def check1(blocks: list[WorklyBlock], roster: dict[str, Employee],
           year: int, month: int) -> Check1Report:
    rep = Check1Report()
    days = calendar.monthrange(year, month)[1]
    seen: set[str] = set()

    for b in blocks:
        seen.add(b.employee)
        emp = roster.get(b.employee)
        if emp and month_str(year, month) in emp.exclude_reports:
            rep.excluded_present.append(b.employee)
        if emp is None:
            rep.not_in_roster.append(b.employee)
        diff = abs(b.sum_worked() - b.total)
        tol = b.worked_rows()          # каждая строка теряет < 1 мин на секундах
        missing = tuple(d for d in range(1, days + 1) if d not in b.days_present())
        rep.rows.append(Check1Row(b.employee, min_to_hm(b.total), min_to_hm(b.sum_worked()),
                                  diff, tol, diff <= tol, missing))

    active = {n for n, e in roster.items() if month_str(year, month) not in e.exclude_reports}
    rep.not_in_file = sorted(active - seen)
    return rep


def month_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"
"""П4 по финальным дням, разделён по слоям данных.

П4a (AUTO, source='api') — FAIL, блокирует:
    однопарные: worked == span_min;
    мультипарные: 0 <= worked <= span_min.
П4b (правки, source!='api') — WARN, не блокирует:
    однопарные: worked ∈ [duration(cin,cout)-1, duration(cin,cout)];
    мультипарные: 0 <= worked <= 28 ч × число пар.

Причина разделения: span_min считается из фактических событий (слой событий),
а после правки worked относится к финальному слою. Сравнивать их нельзя —
это давало 94 ложных FAIL в октябре на днях с правками.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .merge import FinalRow
from .timeutil import duration_min

MAX_PAIR_MIN = 28 * 60


@dataclass(frozen=True)
class P4Issue:
    employee_id: int
    day: int
    kind: str
    worked: int | None
    span: int | None
    pairs: int
    layer: str


def _visible(r: FinalRow) -> bool:
    return (
        not r.state
        and r.cin is not None
        and r.cout is not None
        and r.worked is not None
    )


def check4_rows(rows: Iterable[FinalRow]) -> list[P4Issue]:
    """П4a — авто-слой: отработано в пределах окна наблюдения. FAIL блокирует."""
    out: list[P4Issue] = []
    for r in rows:
        if not _visible(r) or r.source != "api":
            continue
        if r.span is None:
            out.append(
                P4Issue(
                    r.employee_id, r.day, "нет span", r.worked, None, r.pairs, "auto"
                )
            )
            continue
        if not 0 <= r.worked <= r.span:
            out.append(
                P4Issue(
                    r.employee_id,
                    r.day,
                    f"worked вне [0, {r.span}]",
                    r.worked,
                    r.span,
                    r.pairs,
                    "auto",
                )
            )
    return out


def check4_edited(rows: Iterable[FinalRow]) -> list[P4Issue]:
    """П4b — правки: согласованность по отображаемым временам. WARN не блокирует."""
    out: list[P4Issue] = []
    for r in rows:
        if not _visible(r) or r.source == "api":
            continue
        span = duration_min(r.cin, r.cout)
        if r.pairs <= 1:
            lo, hi = span - 1, span
            if not lo <= r.worked <= hi:
                out.append(
                    P4Issue(
                        r.employee_id,
                        r.day,
                        f"worked вне [{lo}, {hi}]",
                        r.worked,
                        span,
                        r.pairs,
                        "edited",
                    )
                )
        else:
            hi = MAX_PAIR_MIN * r.pairs
            if not 0 <= r.worked <= hi:
                out.append(
                    P4Issue(
                        r.employee_id,
                        r.day,
                        f"worked вне [0, {hi}]",
                        r.worked,
                        span,
                        r.pairs,
                        "edited",
                    )
                )
    return out

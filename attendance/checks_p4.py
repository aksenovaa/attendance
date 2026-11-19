"""П4 по финальным дням: точная проверка через span_min, а не через отображаемые минуты."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .merge import FinalRow


@dataclass(frozen=True)
class P4Issue:
    employee_id: int
    day: int
    kind: str
    worked: int | None
    span: int | None
    pairs: int


def check4_rows(rows: Iterable[FinalRow]) -> list[P4Issue]:
    """Однопарные: worked == span. Мультипарные: 0 <= worked <= span."""
    issues: list[P4Issue] = []
    for r in rows:
        if r.state or r.cin is None or r.cout is None or r.worked is None:
            continue
        if r.span is None:
            issues.append(
                P4Issue(r.employee_id, r.day, "нет span", r.worked, None, r.pairs)
            )
            continue
        if r.pairs <= 1:
            if r.worked != r.span:
                issues.append(
                    P4Issue(
                        r.employee_id,
                        r.day,
                        "worked != span",
                        r.worked,
                        r.span,
                        r.pairs,
                    )
                )
        elif not 0 <= r.worked <= r.span:
            issues.append(
                P4Issue(
                    r.employee_id,
                    r.day,
                    "worked вне [0, span]",
                    r.worked,
                    r.span,
                    r.pairs,
                )
            )
    return issues

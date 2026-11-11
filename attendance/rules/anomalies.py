"""Детекторы аномалий R1–R6, R9 над строкой дня (чистые функции, без I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..models import ShiftRow
from ..timeutil import duration_min


class Code(str, Enum):
    R1_GLITCH = "R1-glitch"
    R1_RECALC = "R1-recalc"
    R2_NO_OUT = "R2"
    R3_SHIFTED = "R3"
    R4_ZERO = "R4"
    R5_NIGHT = "R5"
    R6_LONG = "R6"
    R9_MIDNIGHT = "R9"


@dataclass(frozen=True)
class Thresholds:
    glitch_min: int = 5
    long_min: int = 14 * 60
    shifted_min: int = 23 * 60


@dataclass(frozen=True)
class Finding:
    code: Code
    employee: str
    day: int
    note: str
    worked: int | None = None


def detect(
    row: ShiftRow,
    shop: str,
    th: Thresholds | None = None,
) -> list[Finding]:
    """Классифицировать строку дня. Порядок проверок = приоритет правил."""
    th = th or Thresholds()
    out: list[Finding] = []
    if row.dayoff:
        return out

    cin, cout, worked = row.cin, row.cout, row.worked
    if cin is None and cout is None:
        return out
    if cin is None or cout is None:
        missing = "нет ухода" if cin is not None else "нет прихода"
        return [Finding(Code.R2_NO_OUT, row.employee, row.day, missing)]

    if worked is not None and worked >= th.shifted_min:
        return [
            Finding(
                Code.R3_SHIFTED,
                row.employee,
                row.day,
                "уход переехал на утро (отработано около 24 ч)",
            )
        ]
    if cin == cout:
        return [Finding(Code.R4_ZERO, row.employee, row.day, "нулевая смена")]

    delta = cout - cin
    if 0 < delta <= th.glitch_min:
        return [
            Finding(Code.R1_GLITCH, row.employee, row.day, f"глюк-пара {delta} мин")
        ]

    expected = duration_min(cin, cout)
    if cout == 0:
        out.append(
            Finding(Code.R9_MIDNIGHT, row.employee, row.day, "уход 00:00 = полночь")
        )
    if delta < 0:
        out.append(
            Finding(Code.R5_NIGHT, row.employee, row.day, "переход через полночь")
        )
    if worked is None or worked != expected:
        out.append(
            Finding(
                Code.R1_RECALC,
                row.employee,
                row.day,
                "отработано не сходится со временами",
                expected,
            )
        )
    if shop == "wide" and expected >= th.long_min:
        out.append(
            Finding(Code.R6_LONG, row.employee, row.day, "длинная смена ШФ — норма")
        )
    return out

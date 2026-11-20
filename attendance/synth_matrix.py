"""Синтез смен по матрице бумажного табеля: часы по дням → пары (приход, уход).

В отличие от синтеза «по сумме» (rules/synthesize), здесь часы первичны из бумаги:
каждый день матрицы даёт одну смену от профильного прихода до приход+часы.
Результат — правки action=set с источником synth_paper, которые идут в общий
конвейер (build → shifts_final → report) и далее в write-back.
"""

from __future__ import annotations

from dataclasses import dataclass

from .intake import Correction
from .timeutil import min_to_hm

DAY_MIN = 24 * 60


@dataclass(frozen=True)
class MatrixDay:
    day: int
    hours: int  # минуты


def build_corrections(
    employee_id: int,
    month: str,
    days: list[MatrixDay],
    profile_in: int = 8 * 60,
    source: str = "synth_paper",
) -> list[Correction]:
    """Строит правки set для каждого дня матрицы (часы > 0)."""
    out: list[Correction] = []
    for d in days:
        if d.hours <= 0:
            continue
        cin = profile_in
        cout = (cin + d.hours) % DAY_MIN  # переход через полночь даёт cout < cin
        out.append(
            Correction(
                employee_id=employee_id,
                day=d.day,
                action="set",
                cin=min_to_hm(cin),
                cout=min_to_hm(cout),
                worked=min_to_hm(d.hours),
                source=source,
                confidence="high",
                note=f"synth from paper matrix {month}",
            )
        )
    return out

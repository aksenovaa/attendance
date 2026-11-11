from __future__ import annotations

import calendar
import random

from ..models import ShiftRow
from ..timeutil import hm_to_min


def synthesize_month(
    employee: str, total_min: int, year: int, month: int, cfg: dict
) -> list[ShiftRow]:
    rnd = random.Random(f"{employee}:{year:04d}-{month:02d}")
    start_base = hm_to_min(cfg["start_base"])
    jitter = int(cfg["start_jitter_min"])
    typical = int(cfg["typical_day_min"])
    p_sat = float(cfg.get("saturday_keep_prob", 0.5))

    days = calendar.monthrange(year, month)[1]
    candidates: list[int] = []
    for d in range(1, days + 1):
        wd = calendar.weekday(year, month, d)
        if wd == 6:
            continue
        if wd == 5 and rnd.random() > p_sat:
            continue
        candidates.append(d)

    n = min(len(candidates), max(1, round(total_min / typical)))

    # ИСПРАВЛЕНИЕ: при n=1 берем просто первый (нулевой) индекс
    if n == 1:
        idx = [0]
    else:
        idx = [round(i * (len(candidates) - 1) / (n - 1)) for i in range(n)]

    chosen = [candidates[i] for i in dict.fromkeys(idx)]
    n = len(chosen)
    base, rem = divmod(total_min, n)
    durs = [base + (1 if i < rem else 0) for i in range(n)]

    rows = []
    for day, dur in zip(chosen, durs):
        cin = start_base + rnd.randint(-jitter, jitter)
        rows.append(ShiftRow(employee, day, cin, cin + dur, dur, source="synth:R9"))
    return rows

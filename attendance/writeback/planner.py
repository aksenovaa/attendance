"""Планировщик вставок для write-back.

Вставляет события только для дней с искусственными данными (правки/реконструкции/синтез),
где утверждённый табель имеет часы, а Workly их не имеет.

НЕ вставляет для дней R2 (ждут скан) — это противоречит правилу R2.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from ..merge import FinalRow
from .models import Insert, InsertPlan

TZ = ZoneInfo("Europe/Moscow")


def plan(
    con: sqlite3.Connection,
    month: str,
    rows: list[FinalRow],
) -> InsertPlan:
    """Планирует вставки для приведения Workly к утверждённому табелю.

    Сейчас — заглушка, возвращает пустой план.
    Реализация: анализ shifts_final vs events_raw, генерация Insert для синтезов.
    """
    run_id = uuid.uuid4().hex[:12]
    inserts: list[Insert] = []

    year, mon = (int(x) for x in month.split("-"))

    for row in rows:
        if row.state:  # пропуск выходных/отпусков
            continue
        if row.source == "api":  # пропускаем авто-слой (ждём скан для R2)
            continue
        if row.worked is None or row.worked <= 0:
            continue

        # Синтез/правка: вставляем пары (приход, уход) из утверждённого табеля
        if row.cin is not None and row.cout is not None:
            day_cin = datetime(
                year, mon, row.day, row.cin // 60, row.cin % 60, tzinfo=TZ
            )
            day_cout = datetime(
                year, mon, row.day, row.cout // 60, row.cout % 60, tzinfo=TZ
            )
            # Переход через полночь: cout < cin → cout следующего дня
            if row.cout < row.cin:
                from datetime import timedelta

                day_cout += timedelta(days=1)

            inserts.append(
                Insert(
                    employee_id=row.employee_id,
                    event_time=day_cin,
                    code=0,  # in
                    reason="synth_insert",
                    source=f"writeback:{run_id}",
                )
            )
            inserts.append(
                Insert(
                    employee_id=row.employee_id,
                    event_time=day_cout,
                    code=1,  # out
                    reason="synth_insert",
                    source=f"writeback:{run_id}",
                )
            )

    return InsertPlan(run_id=run_id, month=month, inserts=inserts)

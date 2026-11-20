"""Планировщик вставок для write-back.

Анализирует shifts_final и events_raw, находит проблемные места:
- R2: нет ухода (unclosed in) → добавить out в конце дня
- Бродячие события (orphan out, бродячий in) → генерация противоположных событий
- R9: синтез для сотрудников без событий → генерация полной смены

Генерирует InsertPlan — список событий для вставки.
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

    Сейчас реализован только R2 (нет ухода).
    """
    run_id = uuid.uuid4().hex[:12]
    inserts: list[Insert] = []

    year, mon = (int(x) for x in month.split("-"))

    for row in rows:
        if row.state:  # пропуск выходных/отпусков
            continue

        # R2: есть приход, нет ухода
        if row.cin is not None and row.cout is None:
            # Добавляем out в конце дня (23:59:59)
            day = datetime(year, mon, row.day, 23, 59, 59, tzinfo=TZ)
            inserts.append(
                Insert(
                    employee_id=row.employee_id,
                    event_time=day,
                    code=1,  # out
                    reason="r2_close",
                    source=f"writeback:{run_id}",
                )
            )

    return InsertPlan(run_id=run_id, month=month, inserts=inserts)

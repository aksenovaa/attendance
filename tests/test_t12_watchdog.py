"""Сторож-тест: t12.work_time корректен (фикс вендора 13.11.2026).

Падает, если вендор снова введёт удвоение (регрессия).
Архитектура остаётся прежней: часы считаем из events_raw (нам нужны пары для write-back),
t12 используем как источник календаря (is_work_day / absence).
"""

from __future__ import annotations

import json

import pytest

from attendance.config import load_settings


def test_t12_work_time_correct() -> None:
    raw = load_settings().data_dir / "raw" / "2026-09" / "api_t12.json"
    if not raw.exists():
        pytest.skip("нет raw-дампа 2026-09")
    t12 = json.loads(raw.read_text("utf-8"))

    # Альфредо 160237, 14.09: эталон 12:05 (725 мин)
    for item in t12:
        if item.get("employee_id") != 160237:
            continue
        for d in (item.get("report") or {}).get("days", []):
            if d["report_date"] != "2026-09-14":
                continue
            work_time = d.get("work_time", "00:00")
            if work_time == "00:00":
                pytest.skip("t12 не содержит день")
            h, m = (int(x) for x in work_time.split(":"))
            minutes = h * 60 + m
            # Вендор исправил удвоение: значение должно быть ≈ 725, а не ≈ 1451.
            assert 600 <= minutes <= 900, (
                f"t12.work_time вышел за норму: 14.09 = {work_time} ({minutes} мин). "
                "Возможно, регрессия удвоения — проверить API."
            )
            return
    pytest.skip("день не найден в t12")

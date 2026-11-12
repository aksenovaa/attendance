"""Сторож-тест: падает, если Workly исправит дефект удвоения t12.

Смысл: мы построили свой расчёт на том факте, что t12 удвоен.
Если вендор это исправит — источник t12 снова станет достоверным,
и надо пересмотреть архитектуру (вернуть его в источники часов).
"""

from __future__ import annotations

import json

import pytest

from attendance.config import load_settings


def test_t12_still_doubled() -> None:
    raw = load_settings().data_dir / "raw" / "2026-09" / "api_t12.json"
    if not raw.exists():
        pytest.skip("нет raw-дампа 2026-09")
    t12 = json.loads(raw.read_text("utf-8"))

    # Альфредо 160237, 14.09: xlsx = 725 мин (12:05)
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
            # Раньше было 1451 (≈ 2 × 725). Если теперь ≈ 725 — дефект исправлен.
            assert minutes >= 1000, (
                f"t12 больше не удвоен: 14.09 = {work_time}. "
                "Вендор исправил дефект — пересмотреть архитектуру (ADR)."
            )
            return
    pytest.skip("день не найден в t12")

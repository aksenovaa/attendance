from __future__ import annotations

import calendar
from pathlib import Path

import yaml

from attendance.rules.synthesize import synthesize_month

CFG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "rules.yaml").read_text("utf-8")
)["synthesis"]["total_only"]


def test_synthesize_invariants():
    rows = synthesize_month("Халбоев Жомшид", 220 * 60, 2026, 9, CFG)

    # Сумма с явным отсеиванием None (хотя мы знаем, что их там нет)
    total_worked = sum(r.worked for r in rows if r.worked is not None)
    assert total_worked == 220 * 60

    assert len({r.day for r in rows}) == len(rows)

    for r in rows:
        wd = calendar.weekday(2026, 9, r.day)
        assert wd != 6

        assert r.cin is not None, "cin не должен быть None для синтезированных смен"
        assert 9 * 60 - 20 <= r.cin <= 9 * 60 + 20

        assert r.cout is not None, "cout не должен быть None"
        assert r.cout >= 19 * 60 - 40

    assert rows == synthesize_month("Халбоев Жомшид", 220 * 60, 2026, 9, CFG)

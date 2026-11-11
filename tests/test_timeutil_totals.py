"""Итоги месяца трёхзначные по часам — парсер обязан их принимать."""

from __future__ import annotations

import pytest

from attendance.timeutil import hm_to_min, is_hm, min_to_hm


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("07:25", 445),
        ("24:00", 1440),
        ("180:12", 10812),
        ("209:54", 12594),
        ("341:34", 20494),
        ("392:30", 23550),
    ],
)
def test_hm_roundtrip(text: str, minutes: int) -> None:
    assert is_hm(text)
    assert hm_to_min(text) == minutes
    assert min_to_hm(minutes) == text

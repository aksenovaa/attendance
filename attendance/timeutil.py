"""Время: минуты/секунды и форматирование.

Часы бывают двузначные (время суток: 07:25) и трёхзначные
(итоги месяца: 180:12, 209:54, 341:34) — принимаем до трёх цифр.
"""

from __future__ import annotations

import re

_HM = re.compile(r"^(\d{1,3}):([0-5]\d)$")
_HMS = re.compile(r"^(\d{1,2}):([0-5]\d):([0-5]\d)$")


def hm_to_min(value: str) -> int:
    match = _HM.match(value.strip())
    if not match:
        raise ValueError(f"не HH:MM: {value!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def is_hm(value: str) -> bool:
    return _HM.match(value.strip()) is not None


def min_to_hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hms_to_sec(value: str) -> int:
    match = _HMS.match(value.strip())
    if not match:
        raise ValueError(f"не HH:MM:SS: {value!r}")
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def duration_min(cin: int, cout: int) -> int:
    """Длительность; d <= 0 трактуем как переход через полночь (R5)."""
    delta = cout - cin
    return delta + 1440 if delta <= 0 else delta

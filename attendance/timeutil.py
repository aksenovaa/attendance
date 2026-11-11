from __future__ import annotations

import re

_HM = re.compile(r"^(\d{1,2}):([0-5]\d)$")
_HMS = re.compile(r"^(\d{1,2}):([0-5]\d):([0-5]\d)$")


def hm_to_min(s: str) -> int:
    m = _HM.match(s.strip())
    if not m:
        raise ValueError(f"не HH:MM: {s!r}")
    return int(m[1]) * 60 + int(m[2])


def is_hm(s: str) -> bool:
    return _HM.match(s.strip()) is not None


def min_to_hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def hms_to_sec(s: str) -> int:
    m = _HMS.match(s.strip())
    if not m:
        raise ValueError(f"не HH:MM:SS: {s!r}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])


def duration_min(cin: int, cout: int) -> int:
    """Длительность; d <= 0 трактуем как переход через полночь (R8)."""
    d = cout - cin
    return d + 1440 if d <= 0 else d

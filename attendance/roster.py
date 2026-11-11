"""Ростер: YAML, алиасы и резолв имён (в т.ч. коротких шапок Workly)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .models import Dept, Employee

DEFAULT_ROSTER = Path(__file__).resolve().parents[1] / "roster" / "employees.yaml"


def load_roster(path: Path = DEFAULT_ROSTER) -> dict[str, Employee]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    result: dict[str, Employee] = {}
    for item in data["employees"]:
        emp = Employee(
            name=item["name"],
            dept=Dept(item["dept"]),
            aliases=tuple(item.get("aliases", ())),
            flags=tuple(item.get("flags", ())),
            exclude_reports=tuple(item.get("exclude_reports", ())),
        )
        result[emp.name] = emp
    return result


@lru_cache(maxsize=1)
def _indexes() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    exact: dict[str, str] = {}
    parts: dict[str, list[str]] = {}
    for name, emp in load_roster().items():
        exact[name.casefold()] = name
        for alias in emp.aliases:
            exact[alias.casefold()] = name
        for part in name.split():
            parts.setdefault(part.casefold(), []).append(name)
    return exact, {key: tuple(names) for key, names in parts.items()}


def resolve_name(raw: str) -> str:
    """Каноническое ФИО по имени, алиасу или уникальной части имени."""
    key = raw.strip().casefold()
    exact, parts = _indexes()
    if key in exact:
        return exact[key]
    candidates = parts.get(key, ())
    if len(candidates) == 1:
        return candidates[0]
    return raw.strip()


def resolve_employee(raw: str, roster: dict[str, Employee]) -> Employee | None:
    return roster.get(resolve_name(raw))


def paper_only(path: Path = DEFAULT_ROSTER) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("paper_only", []))

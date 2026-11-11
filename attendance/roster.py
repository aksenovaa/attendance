from __future__ import annotations

from pathlib import Path

import yaml

from .models import Dept, Employee

DEFAULT_ROSTER = Path(__file__).resolve().parents[1] / "roster" / "employees.yaml"


def load_roster(path: Path = DEFAULT_ROSTER) -> dict[str, Employee]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: dict[str, Employee] = {}
    for d in data["employees"]:
        emp = Employee(
            name=d["name"],
            dept=Dept(d["dept"]),
            aliases=tuple(d.get("aliases", ())),
            flags=tuple(d.get("flags", ())),
            exclude_reports=tuple(d.get("exclude_reports", ())),
        )
        out[emp.name] = emp
    return out


def paper_only(path: Path = DEFAULT_ROSTER) -> list[str]:
    return list(yaml.safe_load(path.read_text(encoding="utf-8")).get("paper_only", []))

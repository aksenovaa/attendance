"""Приём правок: corrections.json / manual CSV → таблица corrections.

Контракт v1 (context/02_API_DATA.md). LLM/оператор не считает отработанное:
worked либо берётся из часов (hours), либо вычисляется при слиянии.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .roster import resolve_name
from .timeutil import is_hm

ACTIONS = {
    "set",
    "add",
    "recon_logout",
    "recon_login",
    "keep",
    "glitch",
    "dayoff",
    "vacation",
    "synth_r9",
}
CONFIDENCE = {"high", "medium", "low"}


@dataclass(frozen=True)
class Correction:
    employee_id: int
    day: int
    action: str
    cin: str | None
    cout: str | None
    worked: str | None
    source: str
    confidence: str
    note: str

    @property
    def accepted(self) -> int:
        return 0 if self.confidence == "low" else 1


def name_to_id(con: sqlite3.Connection) -> dict[str, int]:
    rows = con.execute("SELECT employee_id, full_name FROM employees")
    return {
        resolve_name(" ".join((r["full_name"] or "").split())): r["employee_id"]
        for r in rows
    }


def _clean_time(value: object, field: str, errors: list[str]) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not is_hm(text):
        errors.append(f"{field}: не HH:MM — {text!r}")
        return None
    return text


def _make(
    raw: dict[str, object],
    names: dict[str, int],
    source: str,
    errors: list[str],
) -> Correction | None:
    emp_id = raw.get("employee_id")
    if emp_id in (None, ""):
        name = resolve_name(str(raw.get("employee_raw") or raw.get("employee") or ""))
        emp_id = names.get(name)
        if emp_id is None:
            errors.append(f"сотрудник не найден в ростере: {name!r}")
            return None
    day = int(str(raw.get("day") or 0))
    if not 1 <= day <= 31:
        errors.append(f"день вне 1..31: {day}")
        return None
    action = str(raw.get("action") or "").strip()
    if action not in ACTIONS:
        errors.append(f"неизвестный action: {action!r} (день {day})")
        return None
    confidence = str(raw.get("confidence") or "high").strip()
    if confidence not in CONFIDENCE:
        errors.append(f"confidence: {confidence!r} (день {day})")
        return None
    return Correction(
        employee_id=int(str(emp_id)),
        day=day,
        action=action,
        cin=_clean_time(raw.get("cin"), f"cin д{day}", errors),
        cout=_clean_time(raw.get("cout"), f"cout д{day}", errors),
        worked=_clean_time(
            raw.get("hours") or raw.get("worked"), f"hours д{day}", errors
        ),
        source=source,
        confidence=confidence,
        note=str(raw.get("note") or ""),
    )


def load_json(path: Path, con: sqlite3.Connection, month: str) -> list[Correction]:
    data = json.loads(path.read_text("utf-8"))
    errors: list[str] = []
    if data.get("version") != 1:
        errors.append("version должен быть 1")
    if data.get("month") != month:
        errors.append(f"month в файле {data.get('month')} != {month}")
    src = data.get("source") or {}
    source = f"{src.get('kind', 'manual')}:{src.get('id', path.stem)}"
    names = name_to_id(con)
    items: list[Correction] = []
    for raw in data.get("entries", []):
        item = _make(raw, names, source, errors)
        if item is not None:
            items.append(item)
    low_refs = {
        str(x.get("ref", ""))
        for x in data.get("low_confidence", [])
        if isinstance(x, dict)
    }
    if low_refs:
        items = [
            Correction(**{**it.__dict__, "confidence": "low"})
            if f"entries[{i}]" in low_refs
            else it
            for i, it in enumerate(items)
        ]
    if errors:
        raise ValueError("Ошибки в " + str(path) + ":\n  " + "\n  ".join(errors))
    return items


def load_csv(path: Path, con: sqlite3.Connection, month: str) -> list[Correction]:
    names = name_to_id(con)
    errors: list[str] = []
    items: list[Correction] = []
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            raw = dict(row)
            raw["employee_raw"] = row.get("employee") or row.get("ФИО")
            source = str(row.get("source") or f"manual:{path.stem}")
            item = _make(raw, names, source, errors)
            if item is not None:
                items.append(item)
    if errors:
        raise ValueError("Ошибки в " + str(path) + ":\n  " + "\n  ".join(errors))
    return items


def save(
    con: sqlite3.Connection, month: str, items: list[Correction], source: str
) -> tuple[int, int]:
    """Идемпотентно: заменяем правки этого источника за месяц."""
    con.execute("DELETE FROM corrections WHERE month=? AND source=?", (month, source))
    for it in items:
        con.execute(
            "INSERT INTO corrections (month, employee_id, day, action, cin, cout,"
            " worked, source, confidence, note, accepted) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                month,
                it.employee_id,
                it.day,
                it.action,
                it.cin,
                it.cout,
                it.worked,
                it.source,
                it.confidence,
                it.note,
                it.accepted,
            ),
        )
    con.commit()
    pending = sum(1 for it in items if not it.accepted)
    return len(items), pending


def add_one(con: sqlite3.Connection, month: str, item: Correction) -> int:
    """Добавить одну правку, не затирая другие (точечный ввод из UI)."""
    cur = con.execute(
        "INSERT INTO corrections (month, employee_id, day, action, cin, cout,"
        " worked, source, confidence, note, accepted) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            month,
            item.employee_id,
            item.day,
            item.action,
            item.cin,
            item.cout,
            item.worked,
            item.source,
            item.confidence,
            item.note,
            item.accepted,
        ),
    )
    con.commit()
    return int(cur.lastrowid or 0)


def remove_correction(con: sqlite3.Connection, correction_id: int) -> int:
    cur = con.execute("DELETE FROM corrections WHERE id=?", (correction_id,))
    con.commit()
    return cur.rowcount

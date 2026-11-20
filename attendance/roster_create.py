from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .ingest.workly_api import WorklyClient

DEPT_OFFSET = 35066
LOCATION_DEFAULT = 29384
SCHEDULE_OFFSET_FREE = 83359  # Полиграфия 8-20 (свободный+)
# Workly не позволяет создавать сотрудника задним числом (422 code 8010),
# schedule_start_date обязательное (422 code 8002). Ставим текущую дату.
START_DATE = datetime.now(tz=UTC).date().isoformat()


@dataclass(frozen=True)
class NewEmployee:
    first_name: str
    last_name: str
    key: str  # уникальный ключ для фильтра (--employee)
    tab_number: str = ""
    start_date: str = START_DATE


OFFLINE_EMPLOYEES: tuple[NewEmployee, ...] = (
    NewEmployee("Алик", "Тараненко", key="taranenko"),
    NewEmployee("Владимир", "Карулин", key="karulin"),
    NewEmployee("Игорь", "Юсов", key="yusov"),
)


def next_tab_numbers(con: sqlite3.Connection, count: int) -> list[str]:
    row = con.execute(
        "SELECT MAX(CAST(tab_number AS INTEGER)) FROM employees"
        " WHERE tab_number GLOB '[0-9]*'"
    ).fetchone()
    base = int(row[0] or 0)
    return [str(base + i) for i in range(1, count + 1)]


def build_payload(emp: NewEmployee) -> dict:
    return {
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "department_id": DEPT_OFFSET,
        "locations": [LOCATION_DEFAULT],
        "schedule_id": SCHEDULE_OFFSET_FREE,
        "start_date": emp.start_date,
        "schedule_start_date": emp.start_date,  # обязательное, = start_date
        "tab_number": emp.tab_number,
    }


def ledger_path(settings: Settings) -> Path:
    return settings.data_dir / "ledger" / "employees_create.jsonl"


def create_all(
    settings: Settings,
    con: sqlite3.Connection,
    confirm: bool,
    only: str | None = None,
) -> list[dict]:
    targets = OFFLINE_EMPLOYEES
    if only:
        targets = tuple(
            e for e in targets if e.key == only or e.last_name.lower() == only.lower()
        )
        if not targets:
            raise SystemExit(f"не найден сотрудник: {only}")

    emps = [
        replace(e, tab_number=t)
        for e, t in zip(targets, next_tab_numbers(con, len(targets)), strict=True)
    ]
    payloads = [build_payload(e) for e in emps]
    if not confirm:
        for p in payloads:
            print(json.dumps(p, ensure_ascii=False))
        print(
            f"dry-run: ничего не отправлено (дата старта = {START_DATE}). Повторите с --confirm."
        )
        return []

    client = WorklyClient(settings)
    entries: list[dict] = []
    for emp, payload in zip(emps, payloads, strict=True):
        resp = client.post("employees", payload)
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "payload": payload,
            "response": resp,
        }
        entries.append(entry)
        print(f"создан: {emp.last_name} {emp.first_name} -> {resp.get('id', resp)}")

    path = ledger_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"ledger: {path}")
    return entries

"""Эксперимент write-back на ТЕСТОВОМ сотруднике.

Реальных сотрудников не касается: имя обязано содержать 'ТЕСТ'.
По умолчанию dry-run. Каждый отправленный шаг пишется в локальный ledger.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from attendance.config import load_settings
from attendance.ingest.workly_api import WorklyClient

TZ = ZoneInfo("Europe/Moscow")
MARK = "ТЕСТ"
DEPT = 35064
LOCATION = 29384
SCHEDULE = 83359

STEPS = [
    ("A_in_0800", 0, "08:00:00"),
    ("B_out_1200", 1, "12:00:00"),
    ("C_in_1300", 0, "13:00:00"),
    ("C_out_1800", 1, "18:00:00"),
    ("D_out_1810", 1, "18:10:00"),
    ("D_in_180959", 0, "18:09:59"),
]


def snapshot(client: WorklyClient, emp: int, day: str, out: Path, label: str) -> None:
    inouts = client.get_all(
        "reports/inouts", start_date=day, end_date=day, f="employee", ids=str(emp)
    )
    t12 = client.get_all(
        "reports/t12", start_date=day, end_date=day, f="employee", ids=str(emp)
    )
    mine = [e for e in inouts if e.get("employee_id") == emp]
    print(f"\n--- {label} ---")
    print(f"inouts: {len(mine)} событий")
    for e in mine:
        print("   ", e.get("event_full_date"), e.get("event_name"), e.get("mode"))
    print(f"t12: {len(t12)} записей")
    for item in t12:
        if item.get("employee_id") != emp:
            continue
        for d in (item.get("report") or {}).get("days", []):
            print("   ", d.get("report_date"), "work_time =", d.get("work_time"))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}_inouts.json").write_text(
        json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out / f"{label}_t12.json").write_text(
        json.dumps(t12, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(TZ).date().isoformat())
    parser.add_argument("--employee-id", type=int)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--from-step", type=int, default=0)
    args = parser.parse_args()

    settings = load_settings()
    client = WorklyClient(settings)
    out = settings.data_dir / "raw" / "experiment" / args.date
    ledger = settings.data_dir / "ledger" / f"probe_{args.date}.jsonl"

    emp = args.employee_id
    if emp is None:
        for e in client.get_all("employees"):
            if MARK in (e.get("full_name") or ""):
                emp = e["id"]
                print("Найден тестовый сотрудник:", emp, e["full_name"])
                break
    if emp is None:
        payload = {
            "first_name": "ТЕСТ",
            "last_name": "Табель",
            "department_id": DEPT,
            "locations": [LOCATION],
            "schedule_id": SCHEDULE,
            "start_date": args.date,
            "schedule_start_date": args.date,
            "notes": "служебный, для проверки write-back; удалить после эксперимента",
        }
        print("План создания сотрудника:", json.dumps(payload, ensure_ascii=False))
        if not args.confirm:
            print("--dry-run: ничего не отправлено. Добавьте --confirm.")
            return
        emp = client.post("employees", payload)["id"]
        print("Создан сотрудник:", emp)

    card = client.get(f"employees/{emp}")
    name = (card.get("data") or card).get("full_name") or ""
    if MARK not in name:
        raise SystemExit(f"ОТКАЗ: сотрудник {emp} не тестовый ({name!r})")

    print(f"\nЭксперимент на {emp} ({name.strip()}), дата {args.date}")
    snapshot(client, emp, args.date, out, "before")
    if args.snapshot_only:
        print("\n--snapshot-only: отправка не выполнялась.")
        return

    for idx, (label, code, clock) in enumerate(STEPS):
        if idx < args.from_step:
            print(f"[skip] шаг {idx} {label}")
            continue
        path = "times/clockin" if code == 0 else "times/clockout"
        body = {
            "location_id": LOCATION,
            "employee_id": emp,
            "event_time": f"{args.date} {clock}",
        }
        if not args.confirm:
            print(f"[dry-run] POST {path} {body}")
            continue
        resp = client.post(path, body)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"step": idx, "label": label, "request": body, "response": resp},
                    ensure_ascii=False,
                )
                + "\n"
            )
        snapshot(client, emp, args.date, out, label)

    print("\nГотово. Ledger:", ledger)
    print("Снимки:", out)
    print("Сравните с веб-экспортом за", args.date)


if __name__ == "__main__":
    main()

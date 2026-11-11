"""Таблица сверки событий, веб-экспорта и t12 для тикета вендору."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from attendance.ingest.events import build_days, load_events
from attendance.ingest.workly import parse_summary
from attendance.reconcile import _names
from attendance.timeutil import hm_to_min, is_hm, min_to_hm

ROOT = Path(__file__).resolve().parents[1]
MONTH = "2026-09"


def main() -> None:
    con = sqlite3.connect(ROOT / "data" / "attendance.sqlite")
    con.row_factory = sqlite3.Row
    names = _names(con)
    built = build_days(load_events(con))

    raw = ROOT / "data" / "raw" / MONTH
    t12: dict[tuple[int, str], str] = {}
    for item in json.loads((raw / "api_t12.json").read_text("utf-8")):
        for day in (item.get("report") or {}).get("days", []):
            t12[(item["employee_id"], day["report_date"])] = day.get("work_time") or ""

    xlsx: dict[tuple[str, int], int] = {}
    for path in sorted(p for p in raw.glob("*.xlsx") if "ПриходУход" not in p.name):
        for block in parse_summary(path):
            for row in block.rows:
                xlsx[(block.employee, row.day)] = row.worked or 0

    out = ROOT / "out" / f"workly_bug_evidence_{MONTH}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "employee_id",
                "ФИО",
                "Дата",
                "Приход",
                "Уход",
                "Из событий",
                "Веб-экспорт",
                "t12.work_time",
                "Отношение",
            ]
        )
        for (emp, date), item in sorted(built.items()):
            if not date.startswith(MONTH) or not item.worked:
                continue
            name = names.get(emp)
            if name is None:
                continue
            web = xlsx.get((name, int(date[8:10])), 0)
            api_raw = t12.get((emp, date), "")
            api = hm_to_min(api_raw) if is_hm(api_raw) else 0
            ratio = round(api / web, 3) if web else ""
            writer.writerow(
                [
                    emp,
                    name,
                    date,
                    min_to_hm(item.cin) if item.cin is not None else "",
                    min_to_hm(item.cout) if item.cout is not None else "",
                    min_to_hm(item.worked),
                    min_to_hm(web),
                    api_raw,
                    ratio,
                ]
            )
            rows_written += 1
    print(f"Строк: {rows_written} → {out}")


if __name__ == "__main__":
    main()

"""Диагностика П4: природа расхождений + расчёт правок по ошибочной отметке."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from attendance.config import load_settings
from attendance.ingest.events import Event, build_days, load_events
from attendance.store.db import connect
from attendance.timeutil import hm_to_min, min_to_hm


def deltas(con: sqlite3.Connection, run_id: str) -> None:
    query = (
        "SELECT emp.full_name AS name, sf.day AS day, sf.cin AS cin,"
        " sf.cout AS cout, sf.worked AS worked, sf.pairs AS pairs"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? AND sf.state=''"
        " AND sf.cin IS NOT NULL AND sf.cout IS NOT NULL AND sf.worked IS NOT NULL"
    )
    hist: Counter[int] = Counter()
    other: list[tuple[str, str, int]] = []
    for r in con.execute(query, (run_id,)):
        if r["pairs"] > 1:
            continue
        span = hm_to_min(r["cout"]) - hm_to_min(r["cin"])
        if span < 0:
            span += 1440
        delta = span - hm_to_min(r["worked"])
        hist[delta] += 1
        if delta not in (0, 1):
            other.append((r["name"], r["day"], delta))
    print("Распределение (уход−приход) − отработано, однопарные дни:")
    for delta, count in sorted(hist.items()):
        print(f"  Δ={delta:>3} мин: {count} дней")
    print(f"Вне {{0,1}}: {len(other)}")
    for name, day, delta in other[:20]:
        print(f"  {name} {day} Δ={delta}")


def zhurat(con: sqlite3.Connection, settings: object) -> None:
    row = con.execute(
        "SELECT employee_id, full_name FROM employees WHERE full_name LIKE '%Журат%'"
    ).fetchone()
    eid, name = int(row["employee_id"]), row["full_name"]
    events = [e for e in load_events(con) if e.employee_id == eid]
    window = [
        e for e in events if "2026-11-09" <= e.ts.date().isoformat() <= "2026-11-11"
    ]
    print(f"\n{name} (id={eid}): события 09–11.11")
    for e in window:
        print(f"  {e.ts} {'in ' if e.code == 0 else 'out'} {e.mode}")

    stray = next(
        e
        for e in window
        if e.code == 0 and e.ts.date().isoformat() == "2026-11-10" and e.ts.hour == 0
    )
    fixed = [
        Event(e.employee_id, e.ts, 1 if e is stray else e.code, e.mode) for e in events
    ]

    before = build_days(events)
    after = build_days(fixed)
    print(
        "\nДень       | как сейчас (пары, отработано) | если ошибочный in считать out"
    )
    for day in ("2026-11-09", "2026-11-10", "2026-11-11"):
        b, a = before.get((eid, day)), after.get((eid, day))
        fmt = lambda x: (
            "нет"
            if x is None
            else f"пар={x.pairs} "
            f"{min_to_hm(x.cin) if x.cin is not None else '-'}→"
            f"{min_to_hm(x.cout) if x.cout is not None else '-'} "
            f"{min_to_hm(x.worked) if x.worked is not None else '-'}"
        )
        print(f"{day} | {fmt(b):<28} | {fmt(a)}")

    out = Path(settings.out_dir) / "proposed_corrections_zhurat.csv"  # type: ignore[attr-defined]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "employee",
                "day",
                "cin",
                "cout",
                "hours",
                "action",
                "confidence",
                "source",
                "note",
            ]
        )
        for day in ("2026-11-09", "2026-11-10"):
            a = after.get((eid, day))
            if a is None or a.worked is None:
                continue
            writer.writerow(
                [
                    name,
                    int(day[8:10]),
                    min_to_hm(a.cin) if a.cin is not None else "",
                    min_to_hm(a.cout) if a.cout is not None else "",
                    min_to_hm(a.worked),
                    "set",
                    "high",
                    "decision:zhurat-mistyped-out",
                    "сотрудник отметил приход вместо ухода 10.11 00:11; R10",
                ]
            )
    print(f"\nПредложенные правки (на утверждение): {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="2026-11")
    args = parser.parse_args()
    settings = load_settings()
    con = connect(settings.db_path)
    run_id = str(
        con.execute(
            "SELECT run_id FROM shifts_final WHERE day LIKE ?"
            " ORDER BY rowid DESC LIMIT 1",
            (f"{args.month}%",),
        ).fetchone()["run_id"]
    )
    print(
        f"Месяц {args.month}, run_id={run_id}, сейчас {datetime.now(UTC).isoformat()}"
    )
    deltas(con, run_id)
    zhurat(con, settings)


if __name__ == "__main__":
    main()

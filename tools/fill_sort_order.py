"""Однократно заполняет employees.sort_order из эталонного CSV."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "attendance.sqlite"
GOLDEN = ROOT / "data" / "golden" / "10.2026.Полный табель.csv"


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cols = {r["name"] for r in con.execute("PRAGMA table_info(employees)")}
    if "sort_order" not in cols:
        con.execute("ALTER TABLE employees ADD COLUMN sort_order INTEGER")
        con.commit()
        print("добавлена колонка sort_order")

    name_to_id: dict[str, int] = {}
    for r in con.execute("SELECT employee_id, full_name FROM employees"):
        name_to_id[" ".join((r["full_name"] or "").split())] = r["employee_id"]

    order: list[int] = []
    with GOLDEN.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            name = (row.get("Сотрудник / Итого") or "").strip()
            if not name or name.startswith("Итого"):
                continue
            if name in name_to_id:
                order.append(name_to_id[name])

    for idx, eid in enumerate(order, start=1):
        con.execute("UPDATE employees SET sort_order=? WHERE employee_id=?", (idx, eid))
    con.commit()

    missing = set(name_to_id.values()) - set(order)
    print(f"заполнено sort_order: {len(order)}")
    if missing:
        print("НЕ найдены в эталоне:", missing)
    for r in con.execute(
        "SELECT sort_order, employee_id, full_name FROM employees "
        "WHERE exclude_from_timesheet=0 ORDER BY sort_order"
    ):
        print(f"  {r['sort_order']:>3} {r['employee_id']:>7} {r['full_name']}")


if __name__ == "__main__":
    main()

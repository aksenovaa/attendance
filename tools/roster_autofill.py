"""Автозаполнение shop по department_id; спорные строки — на ручное решение."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "out" / "roster_to_map.csv"
DST = ROOT / "out" / "roster_filled.csv"

SHOP_BY_DEPT = {
    "35066": "offset",  # Полиграфия
    "35065": "wide",  # Широкоформатная печать
}


def main() -> None:
    text = SRC.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines(), delimiter=";"))
    if not rows:
        raise SystemExit(f"Пустой файл: {SRC}")

    unknown: list[dict[str, str]] = []
    for row in rows:
        dept = (row.get("department_id") or "").strip()
        row["shop"] = SHOP_BY_DEPT.get(dept, "")
        if not row["shop"]:
            unknown.append(row)

    with DST.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Записано: {DST}")
    for shop in ("offset", "wide"):
        names = [r["full_name"] for r in rows if r["shop"] == shop]
        print(f"\n{shop} ({len(names)}):")
        for name in names:
            print("  ", name)
    if unknown:
        print("\nБЕЗ ЦЕХА — решить вручную (админу поставить exclude=1):")
        for row in unknown:
            print(
                "  ", row["employee_id"], row["full_name"], "dept", row["department_id"]
            )


if __name__ == "__main__":
    main()

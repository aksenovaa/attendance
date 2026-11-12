#!/usr/bin/env python3
"""Генерирует corrections.csv на основе diff с утверждённым табелем."""

import csv
import re
from pathlib import Path

GOLDEN = Path("data/golden/10.2026.Полный табель.csv")
RAW = Path("out/2026-10.Полный табель.csv")
OUT = Path("out/corrections_2026-10.csv")


def parse_csv(path: Path) -> dict[tuple[str, int], dict]:
    """Возвращает {(employee, day): {cin, cout, worked, tag}}."""
    result = {}
    with path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        current_emp = None
        for row in reader:
            emp = row["Сотрудник / Итого"]
            if emp and emp != "" and not emp.startswith("Итого"):
                current_emp = emp.strip()
                continue
            if not current_emp:
                continue

            date = row["Дата"]
            if not date or not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date):
                continue

            day = int(date.split(".")[0])
            result[(current_emp, day)] = {
                "cin": row["Приход"],
                "cout": row["Уход"],
                "worked": row["Отработано"],
                "tag": row["Метка"],
            }
    return result


def main():
    raw = parse_csv(RAW)
    gold = parse_csv(GOLDEN)

    corrections = []
    for (emp, day), gold_row in gold.items():
        raw_row = raw.get((emp, day), {})

        # пропускаем выходные в эталоне
        if gold_row["cin"] in ("Выходной", "Отпуск", ""):
            continue

        # сравниваем
        if (
            raw_row.get("cin") != gold_row["cin"]
            or raw_row.get("cout") != gold_row["cout"]
            or raw_row.get("worked") != gold_row["worked"]
        ):
            # определяем action
            raw_cin = raw_row.get("cin", "")
            if raw_cin in ("", "Выходной", "Отпуск"):
                action = "add"
            elif gold_row["tag"] == "реконструкция":
                action = "recon_logout"
            else:
                action = "set"

            corrections.append(
                {
                    "employee": emp,
                    "day": day,
                    "cin": gold_row["cin"],
                    "cout": gold_row["cout"],
                    "hours": gold_row["worked"],
                    "action": action,
                    "confidence": "high",
                    "source": "golden",
                    "note": gold_row["tag"],
                }
            )

    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "employee",
                "day",
                "cin",
                "cout",
                "hours",
                "action",
                "confidence",
                "source",
                "note",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(corrections)

    print(f"Сгенерировано {len(corrections)} правок → {OUT}")


if __name__ == "__main__":
    main()

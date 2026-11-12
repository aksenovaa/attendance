"""Извлекает правки из утверждённого табеля (только строки с меткой)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

GOLDEN = Path("data/golden/10.2026.Полный табель.csv")
OUT = Path("out/corrections_2026-10_golden.csv")

TAG_TO_ACTION = {
    "правка": "set",
    "добавлено": "add",
    "реконструкция": "recon_logout",
    "ночь": "keep",
}


def main() -> None:
    corrections: list[dict[str, str]] = []
    with GOLDEN.open(encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        current_emp: str | None = None

        for row in reader:
            if len(row) < 7:
                continue
            col0, date_str, _week, cin, cout, worked, tag = (
                row[0].strip(),
                row[1].strip(),
                row[2].strip(),
                row[3].strip(),
                row[4].strip(),
                row[5].strip(),
                row[6].strip(),
            )

            # строка с именем сотрудника
            if col0 and not col0.startswith("Итого") and not date_str:
                current_emp = col0
                continue

            # строка Итого — пропускаем
            if col0.startswith("Итого") or ";Итого" in col0:
                continue

            # строка дня
            if not current_emp or not date_str:
                continue
            if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
                continue

            day = int(date_str.split(".")[0])

            # Извлекаем ТОЛЬКО строки с меткой
            if tag and tag not in ("Выходной", "Отпуск"):
                action = TAG_TO_ACTION.get(tag, "set")
                corrections.append(
                    {
                        "employee": current_emp,
                        "day": str(day),
                        "cin": cin if cin and cin not in ("Выходной", "Отпуск") else "",
                        "cout": cout,
                        "hours": worked,
                        "action": action,
                        "confidence": "high",
                        "source": "golden",
                        "note": tag,
                    }
                )
            # Выходной в эталоне при наличии данных в raw → dayoff
            elif cin in ("Выходной", "Отпуск") and tag in ("Выходной", "Отпуск"):
                corrections.append(
                    {
                        "employee": current_emp,
                        "day": str(day),
                        "cin": "",
                        "cout": "",
                        "hours": "",
                        "action": "dayoff" if cin == "Выходной" else "vacation",
                        "confidence": "high",
                        "source": "golden",
                        "note": "эталон",
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

    print(f"Извлечено правок из эталона: {len(corrections)} → {OUT}")

    # Статистика по action
    from collections import Counter

    counts = Counter(c["action"] for c in corrections)
    for action, count in counts.most_common():
        print(f"  {action}: {count}")


if __name__ == "__main__":
    main()

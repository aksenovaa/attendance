"""Анализирует расхождения: дни с меткой vs без метки в эталоне."""

from __future__ import annotations

import csv
import re
from pathlib import Path

GOLDEN = Path("data/golden/10.2026.Полный табель.csv")
OURS = Path("out/2026-10.Полный табель.csv")


def parse(path: Path) -> dict[str, dict[int, dict]]:
    result: dict[str, dict[int, dict]] = {}
    with path.open(encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        current_emp: str | None = None
        for row in reader:
            if len(row) < 7:
                continue
            col0, date_str = row[0].strip(), row[1].strip()
            cin, cout, worked, tag = (
                row[3].strip(),
                row[4].strip(),
                row[5].strip(),
                row[6].strip(),
            )
            if col0 and not col0.startswith("Итого") and not date_str:
                current_emp = col0
                result[current_emp] = {}
                continue
            if not current_emp or not date_str:
                continue
            if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
                continue
            day = int(date_str.split(".")[0])
            result[current_emp][day] = {
                "cin": cin,
                "cout": cout,
                "worked": worked,
                "tag": tag,
            }
    return result


def main() -> None:
    golden = parse(GOLDEN)
    ours = parse(OURS)

    with_tag = 0
    without_tag = 0
    examples_with: list[str] = []
    examples_without: list[str] = []

    for emp in golden:
        if emp not in ours:
            continue
        for day, g in sorted(golden[emp].items()):
            o = ours[emp].get(day)
            if o is None:
                continue

            # проверяем расхождения
            g_state = g["cin"] in ("Выходной", "Отпуск")
            o_state = o["cin"] in ("Выходной", "Отпуск")
            if g_state != o_state:
                tag = g["tag"] if g["tag"] not in ("Выходной", "Отпуск") else ""
                if tag:
                    with_tag += 1
                    if len(examples_with) < 5:
                        examples_with.append(f"{emp} д{day:02d}: {tag}")
                else:
                    without_tag += 1
                    if len(examples_without) < 5:
                        examples_without.append(f"{emp} д{day:02d}")
                continue

            if g_state:
                continue

            if g["cin"] != o["cin"] or g["cout"] != o["cout"]:
                tag = g["tag"] if g["tag"] not in ("Выходной", "Отпуск") else ""
                if tag:
                    with_tag += 1
                    if len(examples_with) < 5:
                        examples_with.append(f"{emp} д{day:02d}: {tag}")
                else:
                    without_tag += 1
                    if len(examples_without) < 5:
                        examples_without.append(f"{emp} д{day:02d}")

    print(f"Расхождений с меткой в эталоне: {with_tag}")
    for ex in examples_with:
        print(f"  {ex}")
    print(f"\nРасхождений БЕЗ метки в эталоне: {without_tag}")
    for ex in examples_without:
        print(f"  {ex}")


if __name__ == "__main__":
    main()

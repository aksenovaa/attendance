"""Приёмочная сверка: сравнивает наш табель с эталоном семантически."""

from __future__ import annotations

import csv
import re
from pathlib import Path

OURS = Path("out/2026-10.Полный табель.csv")
GOLDEN = Path("data/golden/10.2026.Полный табель.csv")
TOLERANCE_MIN = 1  # допуск по минутам для строк без метки


def parse_timesheet(path: Path) -> dict[str, dict[int, dict]]:
    """Возвращает {ФИО: {день: {cin, cout, worked, tag}}}"""
    result: dict[str, dict[int, dict]] = {}
    with path.open(encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)  # шапка
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


def hm_to_min(val: str) -> int | None:
    if not val or val in ("Выходной", "Отпуск", "-"):
        return None
    parts = val.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def main() -> None:
    ours = parse_timesheet(OURS)
    golden = parse_timesheet(GOLDEN)

    total_days = 0
    mismatches: list[str] = []

    for emp in golden:
        if emp not in ours:
            mismatches.append(f"НЕТ СОТРУДНИКА: {emp}")
            continue
        for day, g in sorted(golden[emp].items()):
            o = ours[emp].get(day)
            if o is None:
                mismatches.append(f"{emp} д{day:02d}: нет в нашем файле")
                continue
            total_days += 1

            # Сравнение метки
            g_tag = g["tag"] if g["tag"] not in ("Выходной", "Отпуск") else ""
            o_tag = o["tag"] if o["tag"] not in ("Выходной", "Отпуск") else ""
            if g_tag != o_tag:
                mismatches.append(
                    f"{emp} д{day:02d}: метка наша='{o_tag}' эталон='{g_tag}'"
                )

            # Сравнение состояний (Выходной/Отпуск)
            g_state = g["cin"] in ("Выходной", "Отпуск")
            o_state = o["cin"] in ("Выходной", "Отпуск")
            if g_state != o_state:
                mismatches.append(
                    f"{emp} д{day:02d}: состояние наше={o['cin']} эталон={g['cin']}"
                )
                continue

            if g_state:  # оба выходной/отпуск — совпадают
                continue

            # Сравнение времён
            if g["cin"] != o["cin"] or g["cout"] != o["cout"]:
                mismatches.append(
                    f"{emp} д{day:02d}: времена наши={o['cin']}-{o['cout']} "
                    f"эталон={g['cin']}-{g['cout']}"
                )
                continue

            # Сравнение отработанного (с допуском для строк без метки)
            g_min = hm_to_min(g["worked"])
            o_min = hm_to_min(o["worked"])
            if g_min is not None and o_min is not None:
                if abs(g_min - o_min) > TOLERANCE_MIN:
                    mismatches.append(
                        f"{emp} д{day:02d}: отработано наше={o['worked']} "
                        f"эталон={g['worked']} (Δ={abs(g_min - o_min)} мин)"
                    )
                elif abs(g_min - o_min) > 0 and g_tag:
                    mismatches.append(
                        f"{emp} д{day:02d}: Δ{abs(g_min - o_min)} мин на МЕТКЕ "
                        f"'{g_tag}' (наше={o['worked']}, эталон={g['worked']})"
                    )

    print(f"Проверено: {len(golden)} сотрудников, {total_days} дней")
    print(f"Расхождений: {len(mismatches)}")
    if mismatches:
        print("\nПервые 30:")
        for m in mismatches[:30]:
            print(f"  {m}")
    else:
        print("\n✅ ПРИЁМКА ПРОЙДЕНА: табель совпадает с эталоном")


if __name__ == "__main__":
    main()

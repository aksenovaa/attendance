"""Подгонка цикла «N через M» по опорному месяцу и продление на целевой.

Вход: JSON [{"employee", "ref_month", "work_days", "on", "off", "confidence"}].
Выход: качество подгонки (несовпадения) и рабочие дни целевого месяца.
Арифметику и подбор фазы считает Python, человек подтверждает результат.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path


def _month_days(year: int, month: int) -> list[date]:
    out: list[date] = []
    d = date(year, month, 1)
    while d.month == month:
        out.append(d)
        d += timedelta(days=1)
    return out


def _predict(shift: int, days: list[date], on: int, off: int) -> set[date]:
    cycle = on + off
    return {d for d in days if (d.toordinal() + shift) % cycle < on}


def fit(
    work_days: list[int], year: int, month: int, on: int, off: int
) -> tuple[int, set[date]]:
    days = _month_days(year, month)
    given = {date(year, month, d) for d in work_days}
    best_shift, best_mism = 0, given ^ set(days)
    for shift in range(on + off):
        mism = given ^ _predict(shift, days, on, off)
        if len(mism) < len(best_mism):
            best_shift, best_mism = shift, mism
    return best_shift, best_mism


def generate(shift: int, year: int, month: int, on: int, off: int) -> list[int]:
    return [d.day for d in _predict(shift, _month_days(year, month), on, off)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ref", required=True, help="путь к JSON со списком опорных дней"
    )
    parser.add_argument("--target", required=True, help="YYYY-MM")
    args = parser.parse_args()

    ty, tm = (int(x) for x in args.target.split("-"))
    items = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    for item in items:
        ry, rm = (int(x) for x in item["ref_month"].split("-"))
        shift, mism = fit(item["work_days"], ry, rm, item["on"], item["off"])
        target_days = generate(shift, ty, tm, item["on"], item["off"])
        print(f"\n=== {item['employee']} (confidence={item['confidence']}) ===")
        print(f"опорный месяц {item['ref_month']}: несовпадений с циклом = {len(mism)}")
        for d in sorted(mism):
            print(f"  не бьётся: {d.isoformat()}")
        print(f"целевой {args.target}: рабочие дни = {target_days}")
        print("ТРЕБУЕТ подтверждения Андрея до использования в синтезе.")


if __name__ == "__main__":
    main()

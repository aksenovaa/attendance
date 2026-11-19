"""Детектор потерянных часов: отброшенные первые приходы / бродячие уходы.

Сигнал: одиночная пара (pairs<=1), у которой span_min - worked_min > порога.
Для мультипар разрыв законен (промежутки между сменами) — они не флаговуются.
"""

from __future__ import annotations

import argparse

from attendance.config import load_settings
from attendance.store.db import connect
from attendance.timeutil import min_to_hm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--threshold", type=int, default=60)
    args = parser.parse_args()

    settings = load_settings()
    con = connect(settings.db_path)
    run = con.execute(
        "SELECT run_id FROM shifts_final WHERE day LIKE ? ORDER BY rowid DESC LIMIT 1",
        (f"{args.month}%",),
    ).fetchone()[0]

    query = (
        "SELECT emp.full_name AS name, sf.day AS day, sf.cin AS cin, sf.cout AS cout,"
        " sf.worked_min AS worked, sf.span_min AS span, sf.pairs AS pairs"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? AND sf.pairs <= 1"
        " AND sf.span_min IS NOT NULL AND sf.worked_min IS NOT NULL"
        " AND (sf.span_min - sf.worked_min) > ?"
        " ORDER BY (sf.span_min - sf.worked_min) DESC"
    )
    rows = list(con.execute(query, (run, args.threshold)))
    print(
        f"Дней с потенциально потерянными часами "
        f"(одиночная пара, span - worked > {args.threshold} мин): {len(rows)}"
    )
    for r in rows:
        gap = r["span"] - r["worked"]
        print(
            f"  {r['name']:<25} {r['day']}  приход={r['cin']} уход={r['cout']}  "
            f"оплачено={min_to_hm(r['worked'])} окно={min_to_hm(r['span'])} "
            f"разрыв={min_to_hm(gap)}"
        )


if __name__ == "__main__":
    main()

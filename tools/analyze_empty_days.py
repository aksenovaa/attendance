# tools/analyze_empty_days.py
"""Анализирует дни без событий среди прошедших дней ноября."""

import sqlite3
from datetime import date


def analyze():
    conn = sqlite3.connect("data/attendance.sqlite")
    cursor = conn.cursor()

    # Дни до сегодня (12 ноября)
    today = date(2026, 11, 12)

    cursor.execute(
        """
        SELECT sf.employee_id, e.full_name, sf.date, sf.cin, sf.cout, sf.state
        FROM shifts_final sf
        JOIN employees e ON sf.employee_id = e.employee_id
        WHERE sf.month = '2026-11'
          AND sf.date < ?
          AND sf.cin IS NULL
          AND sf.cout IS NULL
          AND sf.state IS NULL
        ORDER BY e.full_name, sf.date
    """,
        (today.isoformat(),),
    )

    empty_days = cursor.fetchall()

    print(f"Дней без событий (до 12.11): {len(empty_days)}\n")

    # Группируем по сотрудникам
    from collections import defaultdict

    by_employee = defaultdict(list)
    for emp_id, name, date_str, *_ in empty_days:
        by_employee[name].append(date_str)

    for name, dates in sorted(by_employee.items()):
        print(f"{name}: {len(dates)} дней")
        for d in dates[:5]:
            print(f"  - {d}")
        if len(dates) > 5:
            print(f"  ... и ещё {len(dates) - 5}")
        print()

    conn.close()


if __name__ == "__main__":
    analyze()

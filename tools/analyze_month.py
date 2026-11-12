"""Анализ месяца: итоги по числовым минутам, состояния, пропуски vs календарь."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from attendance.config import load_settings
from attendance.store.db import connect
from attendance.timeutil import min_to_hm

TZ = ZoneInfo("Europe/Moscow")


def _run_id(con: sqlite3.Connection, month: str) -> str:
    row = con.execute(
        "SELECT run_id FROM shifts_final WHERE day LIKE ? ORDER BY rowid DESC LIMIT 1",
        (f"{month}%",),
    ).fetchone()
    if row is None:
        raise SystemExit(f"Нет собранного табеля за {month}. Сначала build.")
    return str(row["run_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--today", default=datetime.now(TZ).date().isoformat())
    args = parser.parse_args()

    settings = load_settings()
    con = connect(settings.db_path)
    run_id = _run_id(con, args.month)
    print(f"Месяц {args.month}, run_id={run_id}, отсечка «прошедшие» < {args.today}")

    print("\n=== Итого по цехам (весь месяц) ===")
    query = (
        "SELECT emp.shop AS shop, SUM(sf.worked_min) AS total,"
        " COUNT(CASE WHEN sf.cin IS NOT NULL AND sf.state='' THEN 1 END) AS days"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? GROUP BY emp.shop ORDER BY emp.shop"
    )
    for r in con.execute(query, (run_id,)):
        total = r["total"] or 0
        print(f"  {r['shop']:<7} {min_to_hm(total):>9}  рабочих дней: {r['days']}")

    print("\n=== По сотрудникам (прошедшие дни) ===")
    query = (
        "SELECT emp.full_name AS name, emp.shop AS shop,"
        " SUM(sf.worked_min) AS total,"
        " COUNT(CASE WHEN sf.cin IS NOT NULL AND sf.state='' THEN 1 END) AS worked,"
        " COUNT(CASE WHEN sf.state='Отпуск' THEN 1 END) AS vac"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? AND sf.day < ?"
        " GROUP BY emp.employee_id ORDER BY emp.shop, emp.full_name"
    )
    for r in con.execute(query, (run_id, args.today)):
        total = r["total"] or 0
        print(
            f"  {r['shop']:<7} {r['name']:<25} {min_to_hm(total):>9}"
            f"  дней: {r['worked']:>2}  отпуск: {r['vac']:>2}"
        )

    print("\n=== Пропуски: рабочий день по календарю, событий нет ===")
    query = (
        "SELECT emp.full_name AS name, sf.day AS day, df.absence_title AS absence"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " LEFT JOIN day_frame df ON df.employee_id=sf.employee_id AND df.day=sf.day"
        " WHERE sf.run_id=? AND sf.day < ? AND sf.state='Выходной'"
        " AND df.is_work_day=1 AND COALESCE(df.absence_title,'')=''"
        " ORDER BY emp.full_name, sf.day"
    )
    gaps = list(con.execute(query, (run_id, args.today)))
    print(f"Всего: {len(gaps)}")
    for r in gaps[:40]:
        print(f"  {r['name']:<25} {r['day']}")

    print("\n=== Нет ухода (R2) ===")
    query = (
        "SELECT emp.full_name AS name, sf.day AS day, sf.cin AS cin"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? AND sf.day < ? AND sf.state=''"
        " AND sf.cin IS NOT NULL AND sf.cout IS NULL"
        " ORDER BY emp.full_name, sf.day"
    )
    for r in con.execute(query, (run_id, args.today)):
        print(f"  {r['name']:<25} {r['day']} приход={r['cin']}")

    print("\n=== Мультипары (П4 ослаблен) ===")
    query = (
        "SELECT emp.full_name AS name, sf.day AS day, sf.pairs AS pairs,"
        " sf.cin AS cin, sf.cout AS cout, sf.worked AS worked"
        " FROM shifts_final sf JOIN employees emp ON emp.employee_id=sf.employee_id"
        " WHERE sf.run_id=? AND sf.pairs > 1 ORDER BY emp.full_name, sf.day"
    )
    for r in con.execute(query, (run_id,)):
        print(
            f"  {r['name']:<25} {r['day']} пар={r['pairs']}"
            f" {r['cin']}→{r['cout']} отработано={r['worked']}"
        )

    print("\n=== Календарь day_frame: покрытие ===")
    row = con.execute(
        "SELECT COUNT(*) AS n, MIN(day) AS first, MAX(day) AS last"
        " FROM day_frame WHERE day LIKE ?",
        (f"{args.month}%",),
    ).fetchone()
    print(f"  строк: {row['n']}, диапазон: {row['first']} … {row['last']}")
    print("  work_time из day_frame НЕ используется (дефект удвоения).")


if __name__ == "__main__":
    main()

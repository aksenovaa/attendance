"""CLI: probe / roster-sync / pull."""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import load_settings
from .ingest.workly_api import WorklyClient
from .intake import load_csv, load_json, save
from .merge import build_final, check3
from .reconcile import reconcile, write_report
from .reconcile_events import reconcile_events
from .report.csv_ import write as write_csv
from .store.db import connect


def _month_bounds(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last:02d}"


def _save_raw(data_dir: Path, month: str, name: str, payload: Any) -> None:
    path = data_dir / "raw" / month
    path.mkdir(parents=True, exist_ok=True)
    (path / f"api_{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def cmd_probe(_: argparse.Namespace) -> None:
    settings = load_settings()
    client = WorklyClient(settings)
    account = client.get("accounts")
    print("company:", account.get("company_name"))
    print("tz:", account["settings"]["time_zone"])
    print("employees:", len(client.get_all("employees")))


def cmd_roster_sync(_: argparse.Namespace) -> None:
    settings = load_settings()
    client = WorklyClient(settings)
    con = connect(settings.db_path)
    for row in client.get_all("departments"):
        con.execute(
            "INSERT OR REPLACE INTO departments (department_id, title, pid)"
            " VALUES (?,?,?)",
            (row.get("id"), row.get("title"), _scalar(row.get("pid"))),
        )
    for row in client.get_all("locations"):
        con.execute(
            "INSERT OR REPLACE INTO locations (location_id, title) VALUES (?,?)",
            (row.get("id"), row.get("title")),
        )
    for row in client.get_all("schedules"):
        con.execute(
            "INSERT OR REPLACE INTO schedules (schedule_id, title, type)"
            " VALUES (?,?,?)",
            (row.get("id"), row.get("title"), _scalar(row.get("type"))),
        )
    con.commit()
    print("departments:")
    for r in con.execute("SELECT department_id, title FROM departments"):
        print("  ", r["department_id"], r["title"])
    print("schedules:")
    for r in con.execute("SELECT schedule_id, title, type FROM schedules"):
        print("  ", r["schedule_id"], r["title"], r["type"])
    employees = client.get_all("employees")
    for emp in employees:
        con.execute(
            "INSERT OR REPLACE INTO employees (employee_id, tab_number, pin_code,"
            " full_name, department_id, position_title, schedule_id, start_date)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                emp["id"],
                emp.get("tab_number"),
                emp.get("pin_code"),
                emp.get("full_name"),
                (emp.get("department") or {}).get("id"),
                (emp.get("positions") or [{}])[0].get("title"),
                (emp.get("schedule") or {}).get("id"),
                emp.get("start_date"),
            ),
        )
    con.commit()
    settings.out_dir.mkdir(parents=True, exist_ok=True)
    out = settings.out_dir / "roster_to_map.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "employee_id",
                "tab_number",
                "full_name",
                "department_id",
                "position",
                "start_date",
                "shop",
                "exclude",
            ]
        )
        for row in con.execute("SELECT * FROM employees ORDER BY full_name"):
            writer.writerow(
                [
                    row["employee_id"],
                    row["tab_number"],
                    row["full_name"],
                    row["department_id"],
                    row["position_title"],
                    row["start_date"],
                    row["shop"] or "",
                    row["exclude_from_timesheet"],
                ]
            )
    print(f"employees: {len(employees)} → {out}")
    print("Заполните shop (offset|wide) и exclude=1 для админа, затем roster-apply.")


def cmd_pull(args: argparse.Namespace) -> None:
    settings = load_settings()
    client = WorklyClient(settings)
    con = connect(settings.db_path)
    start, end = _month_bounds(args.month)
    run_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    con.execute(
        "INSERT INTO runs (run_id, month, started_at, status) VALUES (?,?,?,?)",
        (run_id, args.month, now, "running"),
    )
    events = client.get_all("reports/inouts", start_date=start, end_date=end)
    _save_raw(settings.data_dir, args.month, "inouts", events)
    for ev in events:
        key = f"{ev['employee_id']}|{ev['event_full_date']}|{ev['event_code']}"
        con.execute(
            "INSERT OR REPLACE INTO events_raw (event_key, employee_id,"
            " event_full_date, event_code, mode, location_id, serial_number,"
            " source, pulled_at, run_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                key,
                ev["employee_id"],
                ev["event_full_date"],
                ev["event_code"],
                ev.get("mode"),
                ev.get("location_id"),
                ev.get("serial_number"),
                "api",
                now,
                run_id,
            ),
        )
    t12 = client.get_all("reports/t12", start_date=start, end_date=end)
    _save_raw(settings.data_dir, args.month, "t12", t12)
    days = 0
    for item in t12:
        for day in (item.get("report") or {}).get("days", []):
            days += 1
            con.execute(
                "INSERT OR REPLACE INTO day_frame (employee_id, day, is_work_day,"
                " is_holiday, work_time, absence_title, source, run_id)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    item["employee_id"],
                    day["report_date"],
                    int(bool(day.get("is_work_day"))),
                    int(bool(day.get("is_holiday"))),
                    day.get("work_time"),
                    day.get("absence_cause_title"),
                    "api",
                    run_id,
                ),
            )
    con.execute(
        "UPDATE runs SET finished_at=?, status='ok' WHERE run_id=?", (now, run_id)
    )
    con.commit()
    print(f"{args.month}: events={len(events)}, t12 employees={len(t12)}, days={days}")
    print(f"run_id={run_id}, raw → data/raw/{args.month}/")


def cmd_roster_apply(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    updated = 0
    with Path(args.file).open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            con.execute(
                "UPDATE employees SET shop=?, exclude_from_timesheet=? WHERE employee_id=?",
                (
                    (row.get("shop") or "").strip() or None,
                    int(row.get("exclude") or 0),
                    int(row["employee_id"]),
                ),
            )
            updated += 1
    con.commit()
    print(f"roster обновлён: {updated} строк")


def main() -> None:
    parser = argparse.ArgumentParser(prog="attendance")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # S1 команды
    sub.add_parser("probe").set_defaults(func=cmd_probe)
    sub.add_parser("roster-sync").set_defaults(func=cmd_roster_sync)

    p_pull = sub.add_parser("pull")
    p_pull.add_argument("--month", required=True)
    p_pull.set_defaults(func=cmd_pull)

    p_apply = sub.add_parser("roster-apply")
    p_apply.add_argument("--file", required=True)
    p_apply.set_defaults(func=cmd_roster_apply)

    p_re = sub.add_parser("reconcile-events")
    p_re.add_argument("--month", required=True)
    p_re.set_defaults(func=cmd_reconcile_events)

    p_rec = sub.add_parser("reconcile")
    p_rec.add_argument("--month", required=True)
    p_rec.set_defaults(func=cmd_reconcile)

    # S2 команды — ПЕРЕД parse_args()
    p_ca = sub.add_parser("corrections-add")
    p_ca.add_argument("--month", required=True)
    p_ca.add_argument("--file", required=True)
    p_ca.set_defaults(func=cmd_corrections_add)

    p_cr = sub.add_parser("corrections-review")
    p_cr.add_argument("--month", required=True)
    p_cr.set_defaults(func=cmd_corrections_review)

    p_cc = sub.add_parser("corrections-accept")
    p_cc.add_argument("--id", type=int, action="append", required=True)
    p_cc.set_defaults(func=cmd_corrections_accept)

    p_b = sub.add_parser("build")
    p_b.add_argument("--month", required=True)
    p_b.set_defaults(func=cmd_build)

    p_rp = sub.add_parser("report")
    p_rp.add_argument("--month", required=True)
    p_rp.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


def _scalar(value: object) -> object:
    """SQLite принимает только скаляры: вложенные dict/list отбрасываем."""
    if isinstance(value, dict | list):
        return None
    return value


def _title_of(value: object) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            title = first.get("title")
            return str(title) if title is not None else None
    return None


def cmd_reconcile(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    raw = settings.data_dir / "raw" / args.month
    paths = sorted(p for p in raw.glob("*.xlsx") if "ПриходУход" not in p.name)
    if not paths:
        raise SystemExit(f"Нет сводных xlsx в {raw}")
    diffs, common = reconcile(con, args.month, paths)
    out = settings.out_dir / f"reconcile_{args.month}.csv"
    write_report(diffs, out)
    print(f"{args.month}: общих дней={common}, расхождений={len(diffs)} → {out}")
    for diff in diffs[:20]:
        print(
            f"  {diff.employee} {diff.day:02d} {diff.field}: {diff.api} / {diff.xlsx}"
        )


def cmd_reconcile_events(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    raw = settings.data_dir / "raw" / args.month
    paths = sorted(p for p in raw.glob("*.xlsx") if "ПриходУход" not in p.name)
    if not paths:
        raise SystemExit(f"Нет сводных xlsx в {raw}")
    diffs, common = reconcile_events(con, args.month, paths)
    out = settings.out_dir / f"reconcile_events_{args.month}.csv"
    write_report(diffs, out)
    print(f"{args.month}: общих дней={common}, расхождений={len(diffs)} → {out}")
    for diff in diffs[:25]:
        print(
            f"  {diff.employee} {diff.day:02d} {diff.field}: {diff.api} / {diff.xlsx}"
        )


def cmd_corrections_add(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    path = Path(args.file)
    items = (
        load_csv(path, con, args.month)
        if path.suffix.lower() == ".csv"
        else load_json(path, con, args.month)
    )
    source = items[0].source if items else path.stem
    count, pending = save(con, args.month, items, source)
    print(f"{args.month}: принято {count}, в очередь подтверждения {pending}")


def cmd_corrections_review(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    query = (
        "SELECT c.id, e.full_name, c.day, c.action, c.cin, c.cout, c.worked,"
        " c.source, c.note FROM corrections c JOIN employees e"
        " ON e.employee_id = c.employee_id"
        " WHERE c.month=? AND c.accepted=0 ORDER BY e.full_name, c.day"
    )
    rows = list(con.execute(query, (args.month,)))
    if not rows:
        print("Очередь пуста.")
        return
    for r in rows:
        print(
            f"[{r['id']}] {r['full_name']} д{r['day']:02d} {r['action']}"
            f" {r['cin'] or '-'}→{r['cout'] or '-'} ({r['worked'] or '-'})"
            f" | {r['source']} | {r['note']}"
        )
    print("\nПринять: attendance corrections-accept --id N [--id M ...]")


def cmd_corrections_accept(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    for item in args.id:
        con.execute("UPDATE corrections SET accepted=1 WHERE id=?", (item,))
    con.commit()
    print(f"Принято правок: {len(args.id)}")


def cmd_build(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    run_id = uuid.uuid4().hex[:12]
    rows = build_final(con, args.month, run_id)
    report = check3(con, args.month, run_id, rows)
    bad = [r for r in report if not r.ok]
    print(f"{args.month}: строк {len(rows)}, run_id={run_id}, П3 FAIL={len(bad)}")
    for r in bad:
        print(f"  emp={r.employee_id}: {r.base} + {r.delta} != {r.final}")
    (settings.data_dir / "last_run.txt").write_text(run_id, encoding="utf-8")


def cmd_report(args: argparse.Namespace) -> None:
    settings = load_settings()
    con = connect(settings.db_path)
    run_id = (settings.data_dir / "last_run.txt").read_text("utf-8").strip()
    rows = build_final(con, args.month, run_id)
    names = {
        r["employee_id"]: " ".join((r["full_name"] or "").split())
        for r in con.execute("SELECT employee_id, full_name FROM employees")
    }
    # извлекаем порядок из rows (build_final уже отсортировал по sort_order)
    order: list[int] = []
    seen: set[int] = set()
    for r in rows:
        if r.employee_id not in seen:
            order.append(r.employee_id)
            seen.add(r.employee_id)
    out = settings.out_dir / f"{args.month}.Полный табель.csv"
    write_csv(out, args.month, rows, names, order=order)
    print(f"Записано: {out}")


if __name__ == "__main__":
    main()

"""Слияние: дни из событий + правки → shifts_final + audit. Проверка П3."""

from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .ingest.events import build_days, load_events
from .timeutil import duration_min, hm_to_min, min_to_hm

TAGS = {
    "set": "правка",
    "add": "добавлено",
    "recon_logout": "реконструкция",
    "recon_login": "правка",
    "synth_r9": "реконструкция",
    "glitch": "глюк",
}


@dataclass(frozen=True)
class FinalRow:
    employee_id: int
    day: int
    cin: int | None
    cout: int | None
    worked: int | None
    state: str
    tag: str
    source: str
    pairs: int


@dataclass(frozen=True)
class Check3Row:
    employee_id: int
    base: int
    delta: int
    final: int

    @property
    def ok(self) -> bool:
        return self.base + self.delta == self.final


def _corrections(
    con: sqlite3.Connection, month: str
) -> dict[tuple[int, int], list[sqlite3.Row]]:
    grouped: dict[tuple[int, int], list[sqlite3.Row]] = {}
    query = (
        "SELECT * FROM corrections WHERE month=? AND accepted=1 "
        "ORDER BY employee_id, day, id"
    )
    for row in con.execute(query, (month,)):
        grouped.setdefault((row["employee_id"], row["day"]), []).append(row)
    return grouped


def _apply(slot: dict[str, object], c: sqlite3.Row) -> None:
    action = c["action"]
    if action == "keep":
        return
    if action in ("dayoff", "vacation"):
        slot.update(
            state="Выходной" if action == "dayoff" else "Отпуск",
            cin=None,
            cout=None,
            worked=None,
        )
        return
    if action == "glitch":
        slot.update(state="", worked=0)
        return
    if c["cin"]:
        slot["cin"] = hm_to_min(c["cin"])
    if c["cout"]:
        slot["cout"] = hm_to_min(c["cout"])
    cin, cout = slot["cin"], slot["cout"]
    if action == "recon_logout" and not c["cout"] and c["worked"] and cin is not None:
        slot["cout"] = (int(cin) + hm_to_min(c["worked"])) % 1440
    if action == "recon_login" and not c["cin"] and c["worked"] and cout is not None:
        slot["cin"] = (int(cout) - hm_to_min(c["worked"])) % 1440
    if c["worked"]:
        slot["worked"] = hm_to_min(c["worked"])
    elif slot["cin"] is not None and slot["cout"] is not None:
        slot["worked"] = duration_min(int(slot["cin"]), int(slot["cout"]))
    slot["state"] = ""


def build_final(con: sqlite3.Connection, month: str, run_id: str) -> list[FinalRow]:
    year, mon = (int(x) for x in month.split("-"))
    ndays = calendar.monthrange(year, mon)[1]
    built = build_days(load_events(con))
    corr = _corrections(con, month)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    employees = [
        r["employee_id"]
        for r in con.execute(
            "SELECT employee_id FROM employees WHERE exclude_from_timesheet=0"
            " ORDER BY shop, full_name"
        )
    ]
    con.execute("DELETE FROM shifts_final WHERE run_id=?", (run_id,))
    result: list[FinalRow] = []
    for eid in employees:
        for day in range(1, ndays + 1):
            iso = date(year, mon, day).isoformat()
            b = built.get((eid, iso))
            slot: dict[str, object] = {
                "cin": b.cin if b else None,
                "cout": b.cout if b else None,
                "worked": b.worked if b else None,
                "state": "" if b and b.cin is not None else "Выходной",
                "tag": "",
                "source": "api",
                "pairs": b.pairs if b else 0,
            }
            before = dict(slot)
            for c in corr.get((eid, day), []):
                _apply(slot, c)
                slot["tag"] = TAGS.get(c["action"], "правка")
                slot["source"] = c["source"]
            for field in ("cin", "cout", "worked", "state"):
                if before[field] != slot[field]:
                    con.execute(
                        "INSERT INTO audit (run_id, employee_id, day, field,"
                        " old_value, new_value, rule, source, ts)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            run_id,
                            eid,
                            iso,
                            field,
                            str(before[field]),
                            str(slot[field]),
                            str(slot["tag"]),
                            str(slot["source"]),
                            now,
                        ),
                    )
            row = FinalRow(
                employee_id=eid,
                day=day,
                cin=slot["cin"],  # type: ignore[arg-type]
                cout=slot["cout"],  # type: ignore[arg-type]
                worked=slot["worked"],  # type: ignore[arg-type]
                state=str(slot["state"]),
                tag=str(slot["tag"]),
                source=str(slot["source"]),
                pairs=int(slot["pairs"]),  # type: ignore[arg-type]
            )
            con.execute(
                "INSERT OR REPLACE INTO shifts_final (employee_id, day, cin, cout,"
                " worked, tag, source, rule, run_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    eid,
                    iso,
                    min_to_hm(row.cin) if row.cin is not None else None,
                    min_to_hm(row.cout) if row.cout is not None else None,
                    min_to_hm(row.worked) if row.worked is not None else None,
                    row.tag,
                    row.source,
                    "",
                    run_id,
                ),
            )
            result.append(row)
    con.commit()
    return result


def check3(
    con: sqlite3.Connection, month: str, run_id: str, rows: list[FinalRow]
) -> list[Check3Row]:
    """П3: базовый итог + сумма дельт аудита = итоговый итог."""
    year, mon = (int(x) for x in month.split("-"))
    ndays = calendar.monthrange(year, mon)[1]
    built = build_days(load_events(con))
    out: list[Check3Row] = []
    for eid in sorted({r.employee_id for r in rows}):
        base = 0
        for day in range(1, ndays + 1):
            b = built.get((eid, date(year, mon, day).isoformat()))
            if b and b.worked:
                base += b.worked
        final = sum(r.worked or 0 for r in rows if r.employee_id == eid)
        delta = 0
        query = (
            "SELECT old_value, new_value FROM audit"
            " WHERE run_id=? AND employee_id=? AND field='worked'"
        )
        for a in con.execute(query, (run_id, eid)):
            old = 0 if a["old_value"] in ("None", "") else int(a["old_value"])
            new = 0 if a["new_value"] in ("None", "") else int(a["new_value"])
            delta += new - old
        out.append(Check3Row(eid, base, delta, final))
    return out

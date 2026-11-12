"""Слияние: дни из событий + правки → shifts_final + audit. Проверка П3."""

from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .ingest.events import build_days, load_events
from .timeutil import duration_min, hm_to_min, min_to_hm
from .vacations import days_by_employee

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


class _Slot:
    """Изменяемое состояние дня (типизировано явно, без object)."""

    __slots__ = ("cin", "cout", "pairs", "source", "state", "tag", "worked")

    def __init__(
        self,
        cin: int | None,
        cout: int | None,
        worked: int | None,
        state: str,
        pairs: int,
    ) -> None:
        self.cin = cin
        self.cout = cout
        self.worked = worked
        self.state = state
        self.pairs = pairs
        self.tag = ""
        self.source = "api"

    def snapshot(self) -> tuple[int | None, int | None, int | None, str]:
        return (self.cin, self.cout, self.worked, self.state)

    def restore(self, snap: tuple[int | None, int | None, int | None, str]) -> None:
        self.cin, self.cout, self.worked, self.state = snap


def _apply(slot: _Slot, c: sqlite3.Row) -> None:
    action = c["action"]
    if action == "keep":
        return
    if action in ("dayoff", "vacation"):
        slot.state = "Выходной" if action == "dayoff" else "Отпуск"
        slot.cin = None
        slot.cout = None
        slot.worked = None
        return
    if action == "glitch":
        slot.state = ""
        slot.worked = 0
        return

    if c["cin"]:
        slot.cin = hm_to_min(c["cin"])
    if c["cout"]:
        slot.cout = hm_to_min(c["cout"])

    worked_raw = c["worked"]
    if (
        action == "recon_logout"
        and not c["cout"]
        and worked_raw
        and slot.cin is not None
    ):
        slot.cout = (slot.cin + hm_to_min(worked_raw)) % 1440
    if (
        action == "recon_login"
        and not c["cin"]
        and worked_raw
        and slot.cout is not None
    ):
        slot.cin = (slot.cout - hm_to_min(worked_raw)) % 1440

    if worked_raw:
        slot.worked = hm_to_min(worked_raw)
    elif slot.cin is not None and slot.cout is not None:
        slot.worked = duration_min(slot.cin, slot.cout)
    slot.state = ""


def _employee_order(con: sqlite3.Connection) -> list[int]:
    cols = {r["name"] for r in con.execute("PRAGMA table_info(employees)")}
    if "sort_order" in cols:
        query = (
            "SELECT employee_id FROM employees WHERE exclude_from_timesheet=0 "
            "ORDER BY COALESCE(sort_order, 999), employee_id"
        )
    else:
        query = (
            "SELECT employee_id FROM employees WHERE exclude_from_timesheet=0 "
            "ORDER BY employee_id"
        )
    return [int(r["employee_id"]) for r in con.execute(query)]


def build_final(con: sqlite3.Connection, month: str, run_id: str) -> list[FinalRow]:
    year, mon = (int(x) for x in month.split("-"))
    ndays = calendar.monthrange(year, mon)[1]
    built = build_days(load_events(con))
    corr = _corrections(con, month)
    vac = days_by_employee(con, month)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    employees = _employee_order(con)

    con.execute("DELETE FROM shifts_final WHERE run_id=?", (run_id,))
    result: list[FinalRow] = []
    for eid in employees:
        for day in range(1, ndays + 1):
            iso = date(year, mon, day).isoformat()
            b = built.get((eid, iso))
            slot = _Slot(
                cin=b.cin if b else None,
                cout=b.cout if b else None,
                worked=b.worked if b else None,
                state="" if b and b.cin is not None else "Выходной",
                pairs=b.pairs if b else 0,
            )
            before = slot.snapshot()
            if iso in vac.get(eid, ()):
                slot.state = "Отпуск"
                slot.cin = None
                slot.cout = None
                slot.worked = None
                slot.source = "vacations"
            for c in corr.get((eid, day), []):
                _apply(slot, c)
                slot.tag = TAGS.get(c["action"], "правка")
                slot.source = c["source"]

            fields = ("cin", "cout", "worked", "state")
            for idx, field in enumerate(fields):
                if before[idx] != slot.snapshot()[idx]:
                    con.execute(
                        "INSERT INTO audit (run_id, employee_id, day, field,"
                        " old_value, new_value, rule, source, ts)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            run_id,
                            eid,
                            iso,
                            field,
                            str(before[idx]),
                            str(slot.snapshot()[idx]),
                            slot.tag,
                            slot.source,
                            now,
                        ),
                    )

            row = FinalRow(
                employee_id=eid,
                day=day,
                cin=slot.cin,
                cout=slot.cout,
                worked=slot.worked,
                state=slot.state,
                tag=slot.tag,
                source=slot.source,
                pairs=slot.pairs,
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

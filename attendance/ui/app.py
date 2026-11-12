"""Streamlit UI: тонкий слой над модулями attendance.* (без бизнес-логики).

Сетка табеля read-only: изменения только через форму правки → corrections.
Запуск: streamlit run attendance/ui/app.py
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from attendance.config import load_settings
from attendance.intake import Correction, add_one, remove_correction
from attendance.merge import build_final, check3
from attendance.report.csv_ import order_from_rows
from attendance.report.csv_ import write as write_csv
from attendance.store.db import connect
from attendance.timeutil import is_hm
from attendance.vacations import add as vac_add
from attendance.vacations import listing as vac_list
from attendance.vacations import remove as vac_del

TZ = ZoneInfo("Europe/Moscow")
ACTIONS = [
    "set",
    "add",
    "recon_logout",
    "recon_login",
    "glitch",
    "dayoff",
    "vacation",
    "keep",
]
PAGES = ["Обзор", "Табель", "Правки", "Отпуска", "Действия"]


def _employees(con: sqlite3.Connection) -> dict[int, str]:
    query = (
        "SELECT employee_id, full_name FROM employees"
        " WHERE exclude_from_timesheet=0"
        " ORDER BY COALESCE(sort_order, 999), employee_id"
    )
    return {
        int(r["employee_id"]): " ".join((r["full_name"] or "").split())
        for r in con.execute(query)
    }


def _csv_path(settings: object, month: str) -> Path:
    return settings.out_dir / f"{month}.Полный табель.csv"  # type: ignore[attr-defined]


def _block(df: pd.DataFrame, name: str) -> pd.DataFrame:
    first = df.index[df.iloc[:, 0] == name].tolist()
    if not first:
        return df.iloc[0:0]
    start = first[0]
    col = df.iloc[:, 0]
    mask = (df.index > start) & (col != "") & (~col.str.startswith("Итого"))
    after = df.index[mask].tolist()
    stop = after[0] if after else len(df)
    return df.loc[start : stop - 1]


def page_overview(con: sqlite3.Connection, month: str) -> None:
    st.header(f"Обзор — {month}")
    emp = con.execute(
        "SELECT COUNT(*) FROM employees WHERE exclude_from_timesheet=0"
    ).fetchone()[0]
    events = con.execute(
        "SELECT COUNT(*) FROM events_raw WHERE event_full_date LIKE ?", (f"{month}%",)
    ).fetchone()[0]
    corr = con.execute(
        "SELECT COUNT(*) FROM corrections WHERE month=?", (month,)
    ).fetchone()[0]
    pending = con.execute(
        "SELECT COUNT(*) FROM corrections WHERE month=? AND accepted=0", (month,)
    ).fetchone()[0]
    vac = len(vac_list(con, month))
    cols = st.columns(5)
    for col, label, value in zip(
        cols,
        ["Сотрудников", "Событий", "Правок", "В очереди", "Отпусков"],
        [emp, events, corr, pending, vac],
        strict=True,
    ):
        col.metric(label, value)
    st.caption("Часы считает Python из events_raw. t12 — только календарь.")


def page_table(settings: object, month: str, names: dict[int, str]) -> None:
    st.header(f"Табель — {month}")
    path = _csv_path(settings, month)
    if not path.exists():
        st.warning("Файл не найден. Пересоберите в разделе «Действия».")
        return
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    who = st.selectbox("Сотрудник", ["все", *names.values()])
    view = df if who == "все" else _block(df, who)
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button(
        "Скачать CSV", path.read_bytes(), file_name=path.name, mime="text/csv"
    )
    st.caption("Сетка только для чтения. Правки — в разделе «Правки».")


def page_corrections(
    con: sqlite3.Connection, month: str, names: dict[int, str]
) -> None:
    st.header(f"Правки — {month}")
    with st.form("add_correction", clear_on_submit=True):
        who = st.selectbox("Сотрудник", list(names.values()))
        day = st.number_input("День", min_value=1, max_value=31, value=1)
        action = st.selectbox("Действие", ACTIONS)
        cin = st.text_input("Приход (HH:MM)", "")
        cout = st.text_input("Уход (HH:MM)", "")
        hours = st.text_input("Отработано (HH:MM), для реконструкции", "")
        note = st.text_input("Основание / примечание", "")
        source = st.text_input("Источник", "ui")
        if st.form_submit_button("Добавить правку"):
            bad = [
                f"{label}: {val!r}"
                for label, val in (("приход", cin), ("уход", cout), ("часы", hours))
                if val and not is_hm(val)
            ]
            if bad:
                st.error("Не формат HH:MM — " + "; ".join(bad))
            else:
                eid = next(k for k, v in names.items() if v == who)
                item = Correction(
                    employee_id=eid,
                    day=int(day),
                    action=action,
                    cin=cin or None,
                    cout=cout or None,
                    worked=hours or None,
                    source=f"{source}:{uuid.uuid4().hex[:6]}",
                    confidence="high",
                    note=note,
                )
                cid = add_one(con, month, item)
                st.success(f"Правка id={cid} добавлена. Пересоберите табель.")

    rows = list(
        con.execute(
            "SELECT id, employee_id, day, action, cin, cout, worked, source,"
            " confidence, note, accepted FROM corrections WHERE month=?"
            " ORDER BY employee_id, day, id",
            (month,),
        )
    )
    if not rows:
        st.info("Правок за месяц нет.")
        return
    table = pd.DataFrame(
        [
            {
                "id": r["id"],
                "Сотрудник": names.get(r["employee_id"], str(r["employee_id"])),
                "День": r["day"],
                "Действие": r["action"],
                "Приход": r["cin"] or "",
                "Уход": r["cout"] or "",
                "Часы": r["worked"] or "",
                "Принято": bool(r["accepted"]),
                "Источник": r["source"],
                "Примечание": r["note"],
            }
            for r in rows
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)
    cid = st.number_input("id правки", min_value=1, value=1, key="corr_id")
    left, right = st.columns(2)
    if left.button("Принять (accepted=1)"):
        con.execute("UPDATE corrections SET accepted=1 WHERE id=?", (int(cid),))
        con.commit()
        st.success("Принято.")
    if right.button("Удалить правку"):
        st.success(f"Удалено: {remove_correction(con, int(cid))}")


def page_vacations(con: sqlite3.Connection, month: str, names: dict[int, str]) -> None:
    st.header(f"Отпуска — {month}")
    with st.form("add_vacation", clear_on_submit=True):
        who = st.selectbox("Сотрудник", list(names.values()), key="vac_who")
        start = st.text_input("Начало (YYYY-MM-DD)", f"{month}-01")
        end = st.text_input("Окончание (YYYY-MM-DD)", f"{month}-30")
        reason = st.text_input("Причина", "Отпуск")
        source = st.text_input("Источник", "ui")
        if st.form_submit_button("Добавить период"):
            eid = next(k for k, v in names.items() if v == who)
            try:
                vid = vac_add(con, eid, start, end, reason, source)
                st.success(f"Отпуск id={vid} добавлен. Пересоберите табель.")
            except ValueError as exc:
                st.error(str(exc))
    rows = vac_list(con, month)
    if not rows:
        st.info("Отпусков нет.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": v.id,
                    "Сотрудник": names.get(v.employee_id, str(v.employee_id)),
                    "Начало": v.start_date,
                    "Окончание": v.end_date,
                    "Причина": v.reason,
                    "Источник": v.source,
                }
                for v in rows
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    vid = st.number_input("id отпуска", min_value=1, value=1, key="vac_id")
    if st.button("Удалить период"):
        st.success(f"Удалено: {vac_del(con, int(vid))}")


def page_actions(con: sqlite3.Connection, settings: object, month: str) -> None:
    st.header("Действия")
    st.caption("pull остаётся в CLI: сетевая операция, запускается осознанно.")
    if st.button("Пересобрать табель (build + report)"):
        run_id = uuid.uuid4().hex[:12]
        rows = build_final(con, month, run_id)
        bad = [r for r in check3(con, month, run_id, rows) if not r.ok]
        names = _employees(con)
        out = _csv_path(settings, month)
        write_csv(out, month, rows, names, order=order_from_rows(rows))
        Path(settings.data_dir / "last_run.txt").write_text(  # type: ignore[attr-defined]
            run_id, encoding="utf-8"
        )
        st.success(f"Строк: {len(rows)}, run_id={run_id}, П3 FAIL={len(bad)}")
        st.write(str(out))
        for r in bad:
            st.error(f"emp={r.employee_id}: {r.base}+{r.delta} != {r.final}")


def main() -> None:
    st.set_page_config(page_title="Табель — Арт Полиграфия", layout="wide")
    settings = load_settings()
    con = connect(settings.db_path)
    names = _employees(con)
    st.sidebar.title("Табель")
    month = st.sidebar.text_input("Месяц (YYYY-MM)", datetime.now(TZ).strftime("%Y-%m"))
    page = st.sidebar.radio("Раздел", PAGES)
    if page == "Обзор":
        page_overview(con, month)
    elif page == "Табель":
        page_table(settings, month, names)
    elif page == "Правки":
        page_corrections(con, month, names)
    elif page == "Отпуска":
        page_vacations(con, month, names)
    else:
        page_actions(con, settings, month)


main()

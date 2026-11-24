"""Резервная копия БД: онлайн-копия с проверкой целостности и счётчиков.

Паттерн INF-7 из портфельного анализа: копия проверяется сразу (integrity_check
+ сверка счётчиков ключевых таблиц); непригодная копия удаляется; существующее
имя не перезаписывается (суффикс _02, _03, ...).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings

KEY_TABLES = ("employees", "events_raw", "shifts_final", "corrections", "audit_log")


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _free_path(backups: Path, stamp: str) -> Path:
    dst = backups / f"attendance_{stamp}.sqlite"
    i = 2
    while dst.exists():
        dst = backups / f"attendance_{stamp}_{i:02d}.sqlite"
        i += 1
    return dst


def backup_db(settings: Settings) -> Path:
    src = settings.db_path
    backups = settings.data_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y%m%d_%H%M%S")
    dst = _free_path(backups, stamp)

    con = sqlite3.connect(src)
    try:
        bcon = sqlite3.connect(dst)
        with bcon:
            con.backup(bcon)
        bcon.close()

        chk = sqlite3.connect(dst)
        ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            t: chk.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in KEY_TABLES
            if _table_exists(chk, t)
        }
        chk.close()
    finally:
        con.close()

    if ok != "ok":
        dst.unlink(missing_ok=True)
        raise RuntimeError(f"backup: integrity_check не прошёл: {ok}")

    scon = sqlite3.connect(src)
    try:
        for table, copied in counts.items():
            original = scon.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if original != copied:
                dst.unlink(missing_ok=True)
                raise RuntimeError(
                    f"backup: счётчик {table} не сошёлся: {copied} != {original}"
                )
    finally:
        scon.close()
    return dst

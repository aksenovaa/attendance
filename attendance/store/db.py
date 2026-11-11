"""SQLite: инициализация схемы и подключение."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text("utf-8"))
    return con

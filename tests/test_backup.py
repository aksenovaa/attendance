"""Бэкап БД: онлайн-копия с проверкой целостности и счётчиков."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from attendance.backup import backup_db


def test_backup_creates_verified_copy(tmp_path) -> None:
    src = tmp_path / "att.sqlite"
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE employees (id INTEGER)")
    con.execute("INSERT INTO employees VALUES (1)")
    con.commit()
    con.close()

    settings = SimpleNamespace(db_path=src, data_dir=tmp_path)
    dst = backup_db(settings)

    assert dst.exists()
    chk = sqlite3.connect(dst)
    assert chk.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 1
    chk.close()


def test_backup_does_not_overwrite(tmp_path) -> None:
    src = tmp_path / "att.sqlite"
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE employees (id INTEGER)")
    con.commit()
    con.close()

    settings = SimpleNamespace(db_path=src, data_dir=tmp_path)
    first = backup_db(settings)
    (tmp_path / "backups" / first.name).touch()  # имитация коллизии имени
    second = backup_db(settings)
    assert second != first
    assert second.exists()

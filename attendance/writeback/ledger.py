"""Ledger для write-back: запись и чтение writeback_ledger.jsonl."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import LedgerEntry


def append(entries: list[LedgerEntry], ledger_path: Path) -> None:
    """Добавить записи в ledger (append mode)."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def read(ledger_path: Path, run_id: str | None = None) -> list[LedgerEntry]:
    """Прочитать записи из ledger, опционально фильтруя по run_id."""
    if not ledger_path.exists():
        return []
    entries: list[LedgerEntry] = []
    with ledger_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            data = json.loads(line)
            if run_id and data["run_id"] != run_id:
                continue
            entries.append(
                LedgerEntry(
                    run_id=data["run_id"],
                    employee_id=data["employee_id"],
                    event_time=data["event_time"],
                    code=data["code"],
                    reason=data["reason"],
                    source=data["source"],
                    ts=data["ts"],
                )
            )
    return entries


def now_iso() -> str:
    """Текущее время в ISO format (Europe/Moscow)."""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/Moscow")).isoformat()

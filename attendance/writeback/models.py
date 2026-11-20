"""Модели для write-back: Insert, InsertPlan, LedgerEntry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Insert:
    """Одно событие для вставки в Workly."""

    employee_id: int
    event_time: datetime  # Europe/Moscow
    code: int  # 0=in, 1=out
    reason: str  # "r2_close", "orphan_in_close", "synth_r9"
    source: str  # "writeback:run_xxx"

    def to_dict(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "event_time": self.event_time.isoformat(),
            "code": self.code,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class InsertPlan:
    """План вставок для write-back."""

    run_id: str
    month: str
    inserts: list[Insert]

    def __len__(self) -> int:
        return len(self.inserts)

    def __iter__(self):
        return iter(self.inserts)


@dataclass(frozen=True)
class LedgerEntry:
    """Запись в writeback_ledger.jsonl."""

    run_id: str
    employee_id: int
    event_time: str  # ISO format
    code: int
    reason: str
    source: str
    ts: str  # когда записано

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "employee_id": self.employee_id,
            "event_time": self.event_time,
            "code": self.code,
            "reason": self.reason,
            "source": self.source,
            "ts": self.ts,
        }

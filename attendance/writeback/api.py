"""POST clockin/clockout в Workly + запись в ledger."""

from __future__ import annotations

from ..config import Settings
from ..ingest.workly_api import WorklyClient
from .ledger import append, now_iso
from .models import Insert, LedgerEntry


def apply(
    inserts: list[Insert],
    settings: Settings,
    run_id: str,
    location_id: int = 29384,
) -> list[LedgerEntry]:
    """Отправляет вставки в Workly и пишет в ledger.

    Dry-run должен быть сделан до вызова (caller проверяет --confirm).
    """
    client = WorklyClient(settings)
    entries: list[LedgerEntry] = []
    for ins in inserts:
        event_time = ins.event_time.strftime("%Y-%m-%d %H:%M:%S")
        endpoint = "times/clockin" if ins.code == 0 else "times/clockout"
        payload = {
            "employee_id": ins.employee_id,
            "location_id": location_id,
            "event_time": event_time,
        }
        client.post(endpoint, payload)
        entries.append(
            LedgerEntry(
                run_id=run_id,
                employee_id=ins.employee_id,
                event_time=ins.event_time.isoformat(),
                code=ins.code,
                reason=ins.reason,
                source=ins.source,
                ts=now_iso(),
            )
        )
        kind = "in " if ins.code == 0 else "out"
        print(f"  {kind} emp={ins.employee_id} {event_time}  reason={ins.reason}")
    if entries:
        ledger_path = settings.data_dir / "ledger" / "writeback.jsonl"
        append(entries, ledger_path)
        print(f"ledger: {ledger_path} ({len(entries)} записей)")
    return entries

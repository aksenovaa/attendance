# Архитектура (кратко)

Workly API → ingest (JSON, пагинация, throttle) → store SQLite (events_raw, day_frame, employees)
→ rules R1–R9 (чистые функции + audit) → merge с corrections/decisions → checks П1–П5
→ report (CSV/XLSX/PDF) → [опц.] writeback (планировщик пар, dry-run, ledger).

Слои: ingest/ (api + xlsx fallback + recognized), store/, rules/, merge.py, checks.py, report/, writeback/, cli.py.
Принципы: raw неизменяем; каждая правка с источником; правила детерминированы; FAIL = стоп; LLM не считает.
Подробности: context/00_PROJECT.md, context/02_API_DATA.md, docs/DECISIONS.md.

# RUNBOOK: восстановление attendance

## Когда применять
Повреждена data/attendance.sqlite; потеряны правки; неудачная миграция.

## Шаги
1. Остановить все процессы (CLI, Streamlit).
2. Выбрать копию: `ls -la data/backups/` (имена с суффиксами не перезаписываются).
3. Проверить копию: `sqlite3 data/backups/<file> "PRAGMA integrity_check"` → `ok`.
4. Откатить: `cp data/backups/<file> data/attendance.sqlite`.
5. Пересобрать производные: `attendance build --month YYYY-MM && attendance report --month YYYY-MM`.
6. Сверить с эталоном: `python tools/accept_golden.py` (ожидание — 153 известных расхождения).
7. Если правки после бэкапа потеряны — восстановить из ledger:
   `data/ledger/*.jsonl` (corrections, writeback, employees_create) и повторить вручную.

## Чего НЕ делать
- Не перезаписывать бэкап «поверх» без проверки целостности.
- Не править raw-дампы: они неизменяемы, производные перестраиваются.

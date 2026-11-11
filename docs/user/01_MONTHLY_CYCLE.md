# Месячный цикл (пошагово)

1. **Сбор исходников.** Сложить в data/raw/YYYY-MM/ сканы распечаток с правками, бумажный табель офсета, блокноты.
2. **Выгрузка из Workly.** `attendance pull --month YYYY-MM` (сотрудники, отделы, inouts, t12, absence). Ничего не экспортируем руками.
3. **Оцифровка.** Прогнать сканы через SCAN_PROMPT / PAPER_PROMPT (context/04_PROMPTS.md), сохранить JSON в data/recognized/YYYY-MM/.
4. **Внесение правок.** `attendance corrections add --file ...` (см. 02_CORRECTIONS.md). Всё low confidence уходит в очередь.
5. **Подтверждение.** `attendance corrections review` — принять/отклонить/поправить спорные дни. Без этого они не попадают в итог.
6. **Сверка бумаги.** `attendance compare paper --file paper_YYYY-MM.json` → отчёт out/paper_diff_*.md → подтвердить пакетно.
7. **Сборка и проверки.** `attendance build` + `attendance check`. Любой FAIL = стоп, смотрим таблицу расхождений.
8. **Отчёты.** `attendance report --format csv,xlsx,pdf` → out/. Передать бухгалтерии.
9. **Утверждение.** Руководитель утверждает месяц (фиксируется в data/corrections/decisions.yaml).
10. **Возврат в Workly (опционально).** `attendance writeback --dry-run`, изучить план, затем `--confirm`. См. 03_WRITEBACK.md.
11. **Архив.** Скопировать out/ и data/ledger/ на Диск; `make context-export`; git commit + tag vYYYY.MM-final.

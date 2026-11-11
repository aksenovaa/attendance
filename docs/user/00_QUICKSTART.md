# Быстрый старт (оператор)

## Установка (один раз)
    cd ~/Projects/attendance
    make init                     # venv + зависимости
    cp .env.example .env          # заполнить: WORKLY_CLIENT_ID/SECRET/USERNAME/PASSWORD
    .venv/bin/python -m pip install -U pip

## Проверка доступа
    attendance probe              # компания, TZ, число сотрудников и событий

## Ежемесячно (кратко)
    attendance pull --month 2026-11
    attendance corrections add --file data/recognized/2026-11/scans_*.json
    attendance corrections review
    attendance build --month 2026-11
    attendance check --month 2026-11
    attendance report --month 2026-11 --format csv,xlsx,pdf
    # после утверждения:
    attendance writeback --month 2026-11 --dry-run
    attendance writeback --month 2026-11 --confirm

## Где что
data/raw — исходники (xlsx, сканы, api-дампы); data/recognized — JSON оцифровки;
data/corrections — правки и решения; data/ledger — журнал отправок в Workly;
out — готовые табели и отчёты проверок.

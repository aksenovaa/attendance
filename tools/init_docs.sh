#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p context docs/user tools \
         data/raw data/recognized data/corrections data/ledger out

for p in 'data/' 'out/' '.env' '*.sqlite' '*.sqlite-journal'; do
  grep -qxF "$p" .gitignore 2>/dev/null || echo "$p" >> .gitignore
done

cat > context/00_PROJECT.md <<'EOF'
# Проект attendance — учёт рабочего времени «Арт Полиграфия»
Цель: Workly → Python → утверждённый табель (CSV/XLSX/PDF) для бухгалтерии. Дедлайн инструмента: 30.11.2026.

## Факты системы (проверено 11.11.2026)
- API https://api.workly.io/v1, доки https://dev.workly.io, OAuth2 grant_type=password (+refresh ~30 дней).
- Компания «Арт Полиграфия», TZ **Europe/Moscow**. Сотрудников 25 = 24 работника + 1 админ (Андрей, в табель НЕ входит).
- Отдел в Workly один: 35066 «Полиграфия» → цеха Офсет/ШФ задаёт наш ростер (ключ employee_id / tab_number).
- Локация 29384 «Локация по умолчанию» — нужна для write-back.
- Лимиты: 50 записей/страница, ≤1000 запросов/мин, 429 → backoff.
- События: изменить/удалить НЕЛЬЗЯ, только добавить. День считается по ПАРАМ событий (in→out) в хронологии.
- График ШФ «Свободный+» → /reports/night доступен.
- Payroll/fines в Workly НЕ используются → write-back не влияет на деньги внутри системы.
- Сотрудники: создать/редактировать/уволить/массово добавить — можно. Пароль через API нельзя (password-reset по email). pin_code/qrcode системные.

## Инфраструктура
- WSL ~/Projects/attendance, venv .venv (Python 3.12), pytest/ruff/mypy/pre-commit.
- Git private github.com/aksenovaa/attendance, ветки main (релиз месяца) / dev (работа).
- В git: context/, docs/, код, тесты. ВНЕ git: data/, out/, .env.
- Экспорт контекста: make context-export → /mnt/d/YD/Yandex.Disk/@Работа/сайты/art-poligrafy.ru/Персонал/Контекст/

## Роли
Андрей — постановщик, арбитр спорных дней, утверждает месяц и разрешает write-back.
Ассистент — архитектура, код, оцифровка сканов, отчёты. Арифметику не считает: отдаёт Python.
Источник истины для ФОТ = утверждённый табель; Workly = регистр событий.

## Статус месяцев
2026-09 закрыт (golden). 2026-10 закрыт (golden). 2026-11 — первый месяц на новом конвейере.
1С: интеграция отложена, выход CSV/PDF.
EOF

cat > context/01_RULES.md <<'EOF'
# Правила обработки и проверок

## Приоритет источников
Рукописная правка/скан > Workly (лог событий, затем сводная) > реконструкция по паттерну.
Бумага офсета округлена до 0,5 ч: |Δ| ≤ 30 мин → оставляем Workly.

## Аномалии
R1 глюк-пара/дубль ≤5 мин → удалить локально; если приход+уход есть, а отработано 00:00 → пересчитать.
R2 нет ухода/прихода → часы не начислять; ждать скан, иначе реконструкция.
R3 уход «переехал» на утро (≈24:xx) → локально очистить; в Workly чинится вставкой out в реальный конец + поглощение бродячего события.
R4 приход = уход → глюк, удалить локально.
R5 переход через полночь при утреннем старте — норма; смена по дате ПРИХОДА; отработано = уход − приход + 24 ч.
R6 длинные смены ШФ (14–18 ч) — норма.
R7 допуск бумаги ±30 мин.
R8 «бумажные» сотрудники вне табеля без прямого указания.
R9 «24:00» = полночь; синтез табеля по заявленной сумме часов.

## Метки
добавлено | правка | реконструкция. Состояния: Выходной, Отпуск, нет ухода, глюк.
«ночь» — только если смена началась после обеда и закончилась утром.

## Ночная политика (11.11.2026)
Ночные/утренние значения Workly не обнуляем: оставляем как в дампе (Альфредо 19/22/29.10 = 21:13 / 20:56 / 12:19).

## Write-back (разрешён 11.11.2026)
- Только после утверждения месяца; --dry-run по умолчанию, --confirm для отправки.
- Модель: пары событий. Любое лишнее событие «поглощается» парой в 1 секунду.
- Синтез R9 пушить РАЗРЕШЕНО, но последним, после финального утверждения суммы.
- Ledger обязателен + копия на Диск: в Workly и синтез, и ручные правки имеют mode=manual.
- Удалить отправленное нельзя → повторный push только через планировщик, без дублей.

## Проверки (любой FAIL → стоп + таблица расхождений)
П1 Σ строк = итог Workly (допуск = число рабочих строк); дней = дни месяца; состав = ростер (без админа).
П2 каждая рукописная ячейка разложена; low confidence → очередь подтверждения, в итог не входит.
П3 у каждой метки есть источник; старый итог − удалённое + добавленное = новый.
П4 отработано = уход − приход (+24 ч); нет дублей (сотрудник, день); итоги = Σ строк.
П5 формат: шапка, метки из списка, HH:MM, итоги, пагинация по сотрудникам.

## Запреты
LLM не считает арифметику и не достраивает отсутствующие строки. Нет данных → «нет данных».
EOF

cat > context/02_API_DATA.md <<'EOF'
# API и контракты данных

## Эндпоинты
GET  /v1/accounts                         профиль, settings.time_zone
GET  /v1/employees?page&f&fv&ids          id, tab_number, pin_code, full_name, department, schedule, start_date
GET  /v1/employees/dismissed              уволенные (limit ≤100)
GET  /v1/employees/{id}                   карточка
POST /v1/employees                        создать: first_name*, department_id*, locations*, schedule_id*, start_date*, schedule_start_date*; username=email
POST /v1/sign-in/password-reset           письмо для задания пароля
GET  /v1/departments | /locations | /schedules
GET  /v1/reports/inouts?start_date&end_date&f&ids&page   СЫРЬЁ
GET  /v1/reports/t12?start_date&end_date&f&ids&page      КАРКАС (days[]: report_date, is_work_day, is_holiday, work_time, absence_*)
GET  /v1/reports/night | /absence
POST /v1/times/clockin | /clockout        {location_id*, employee_id, event_time "Y-m-d H:i:s", latitude, longitude, ip}
Редактирование/увольнение/восстановление/удаление уволенного/массовое добавление — разделы доки есть, точные URL уточняем probe.

## Поля inouts
employee_id, tab_number, pin_code, department_id/title, position_title, event_date,
event_full_date (datetime, сек), event_time, event_code (0=in,1=out), event_name,
mode (auto|manual), location_id/title, serial_number, photos.

## Планировщик write-back
1 цепочка событий за месяц ±1 день → 2 симуляция пар → 3 сравнение с утверждённым табелем
→ 4 минимальные вставки (нет out: +out; нет in: +in; бродячий out: +in за 1 с до; бродячий in: +out через 1 с после;
R3: +out в реальный конец дня D + поглощение на D+1) → 5 пересимуляция → 6 dry-run → confirm → POST → контрольный pull.

## Контракт правок corrections.json (v1)
{version, month, source:{kind:scan|manual|paper|decision, id, file},
 entries:[{employee_raw, employee_id?, day, cin?, cout?, hours?, action, confidence, note, pushable}],
 low_confidence:[{ref, reason, candidates}]}
action: set|add|recon_logout|recon_login|keep|glitch|dayoff|vacation|synth_r9. worked считает Python.

## Оцифровка
scans.json — распечатки/блокноты (day, cin/cout/hours, dayoff, vacation, confidence).
paper.json — матрица офсета (employee_raw, day, hours, note) — только часы, без времён.

## Итоговый табель (утверждённый формат)
CSV «;» UTF-8. Шапка: Сотрудник / Итого;Дата;Неделя;Приход;Уход;Отработано;Метка
Блок: ФИО → все дни месяца (DD.MM.YYYY, пон/втор/сред/чет/пят/суб/вос) → «Итого».
Состояния: Выходной, Отпуск. Время HH:MM, итог ЧЧ:ММ (>24 ч допустимо).

## Ростер
shop (offset|wide) — наш атрибут. Админ (Андрей) исключён из табеля.
Известно: Улукбек employee_id=160238, tab_number=25. Полный ростер — roster sync.
EOF

cat > context/03_STATUS.md <<'EOF'
# Статус и решения

## Готово
Каркас (pyproject, Makefile, venv 3.12, pytest/ruff/mypy, pre-commit), git main+dev.
models/timeutil/roster/checks(П1)/rules.synthesize(R9), ingest/workly.py (merged xlsx).
API-клиент + probe: 25 сотрудников, 838 событий за октябрь, TZ Europe/Moscow.
tools/export_context.py, структура context/ + docs/ + data/ + out/.
Golden: сентябрь и октябрь 2026 утверждены.

## Спринты до 30.11.2026
S1 12–16.11: store (SQLite) + ingest API + roster sync + rules R1–R8 + checks П1/П3/П4/П5 + регрессия на golden raw.
S2 17–23.11: intake правок (скан→JSON, CSV/CLI) + очередь подтверждения + compare paper + synth v2 + отчёты CSV/XLSX/PDF; пересборка октября и сверка с утверждённым CSV.
S3 24–30.11: планировщик write-back + эксперимент на тестовом сотруднике + dry-run октября; Streamlit-интерфейс подтверждения; документация; ноябрь на новом конвейере.

## Решения (ADR)
11.11 TZ Europe/Moscow.
11.11 Ночные значения Workly не обнуляем (keep).
11.11 25-й сотрудник = админ, в табель не входит.
11.11 R3 чинится вставкой событий (модель пар), а не «только расширение».
11.11 Write-back разрешён, включая синтез R9; только после утверждения, dry-run + ledger.
11.11 Payroll/fines не используются → write-back безопасен для денег.
11.11 Каналы правок: A (ИИ-скан→JSON) + B (CSV/CLI) сейчас, C (Streamlit) в S3.
11.11 1С отложен; выход CSV/PDF.

## Открытые вопросы
- employee_id админа (после roster sync).
- Строки утверждённого октября без метки, отличающиеся от Workly: источник = «решение руководителя»?
- Пушить ли сентябрь/октябрь ретроактивно или начать с ноября?
- Можно ли удалять события в веб-UI (для отката ошибочного push)?
EOF

cat > context/04_PROMPTS.md <<'EOF'
# Промпты

## SCAN_PROMPT (распечатки с рукописными правками, блокноты)
Ты оцифровываешь скан табеля. Верни ТОЛЬКО JSON, без пояснений.
{"version":1,"month":"YYYY-MM","source":{"kind":"scan","id":"<файл>"},
 "entries":[{"employee_raw":"<как написано>","day":<1-31>,"cin":"HH:MM"|null,"cout":"HH:MM"|null,
 "hours":"HH:MM"|null,"dayoff":false,"vacation":false,"confidence":"high|medium|low","note":"<что видно>"}],
 "low_confidence":[{"ref":"entries[i]","reason":"<почему>","candidates":["..."]}]}
Правила: не считай отработанное и итоги; не выдумывай — не читается → low + candidates;
часы поверх «Выходной» → dayoff=false + note «поверх Выходной»; «24:00» пиши как есть;
имя как на листе; одна ячейка = одна запись.

## PAPER_PROMPT (матрица офсета: сотрудник × день, часы)
ТОЛЬКО JSON: {"version":1,"month":"YYYY-MM","source":{"kind":"paper","id":"<файл>"},
 "cells":[{"employee_raw":"...","day":<1-31>,"hours":"<как написано: 12 / 10,5>","confidence":"..."}],
 "notes":[{"day":<1-31>|null,"employee_raw":"..."|null,"text":"<примечание дословно>"}],
 "low_confidence":[...]}
Часы во времена не переводи; пустые клетки не заполняй; зачёркнутое помечай note.

## REVIEW_BRIEF (сверка бумага ↔ Workly)
Вход: paper.json + дамп Workly. Выход: список расхождений с категориями
match(≤30мин)/paper_only/workly_only/conflict/no_out/glitch и предложением действия.
Времена брать из Workly либо помечать «по аналогии» с указанием дней-образцов. Арифметику не выдумывать.

## SYNTH_BRIEF (табель по заявленной сумме)
Вход: employee_id, месяц, сумма ЧЧ:ММ, источник решения.
Календарь: его прошлые месяцы + t12.is_work_day/is_holiday. Профиль: его история, иначе бригада ШФ.
Распределение: divmod(total, n_days), остаток по +1 мин. cin профильный (seed), cout = cin + worked.
Метка «реконструкция», note = источник решения. Push разрешён после финального утверждения суммы.
EOF

cat > docs/DECISIONS.md <<'EOF'
# Журнал решений (ADR)

| ID | Дата | Решение | Обоснование / последствие |
|---|---|---|---|
| 001 | 11.11.2026 | TZ = Europe/Moscow | из /v1/accounts; все расчёты в MSK, ночные по дате прихода |
| 002 | 11.11.2026 | Ночные значения Workly не обнулять | решение руководителя; Альфредо 19/22/29.10 = 21:13/20:56/12:19 |
| 003 | 11.11.2026 | 25-й сотрудник = админ, вне табеля | ростер: exclude_from_timesheet |
| 004 | 11.11.2026 | Модель write-back = пары событий; R3 чинится вставками | подтверждено практикой ручных правок в веб-UI; проверяем на тестовом сотруднике |
| 005 | 11.11.2026 | Write-back разрешён, включая синтез R9 | строгого учёта нет; признак mode=manual + наш ledger |
| 006 | 11.11.2026 | Payroll/fines в Workly не используются | push не влияет на расчёты внутри Workly |
| 007 | 11.11.2026 | Каналы правок A+B сейчас, C (Streamlit) в S3 | дедлайн 30.11 |
| 008 | 11.11.2026 | 1С отложен, выход CSV/PDF | конфигурация не определена |
| 009 | 11.11.2026 | Сентябрь и октябрь = golden | raw для П1, утверждённый CSV для формата/П4/П5 |
| 010 | 11.11.2026 |Ledger обязателен, копия на Диск | в Workly синтез и ручные правки одинаково mode=manual |
EOF

cat > docs/user/00_QUICKSTART.md <<'EOF'
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
EOF

cat > docs/user/01_MONTHLY_CYCLE.md <<'EOF'
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
EOF

cat > docs/user/02_CORRECTIONS.md <<'EOF'
# Как вносить правки

## Канал A — скан → JSON (основной)
1. Открыть context/04_PROMPTS.md, взять SCAN_PROMPT (или PAPER_PROMPT для матрицы).
2. Приложить скан в чат проекта, отправить промпт.
3. Сохранить ответ как data/recognized/YYYY-MM/scans_<имя>.json.
4. `attendance corrections add --file data/recognized/YYYY-MM/scans_<имя>.json`
Валидатор проверит схему, имена (ростер), диапазоны времён. Ошибки — в отчёт, ничего не «додумывается».

## Канал B — CSV вручную (когда скана нет)
Шаблон data/corrections/manual_YYYY-MM.csv:
    employee;day;cin;cout;hours;action;source;note
    Ковбас Павел;26;07:30;19:45;;add;блокнот MasterKit;приход и уход с листа
    Улукбек;9;;;11:00;recon_logout;табель;11 часов
    Хожиев Ильхом;;;;;vacation;приказ;отпуск весь месяц
Импорт: `attendance corrections add --file data/corrections/manual_YYYY-MM.csv`
Правила: hours ИЛИ cin+cout; action из списка (set/add/recon_logout/recon_login/keep/glitch/dayoff/vacation/synth_r9);
source обязателен; отработанное НЕ заполняем — считает программа.

## Канал C — интерфейс подтверждения (с S3)
`attendance ui` → таблица спорных дней, чекбоксы «принять/отклонить», правка времени на месте, кнопка «сохранить».

## Синтез по заявленной сумме
    attendance synth --employee "Халбоев Жомшид" --total 392:30 --month YYYY-MM --source "решение руководителя <дата>"
Программа построит календарь и профиль по его истории/бригаде, разложит сумму точно, пометит «реконструкция».

## Очередь подтверждения
`attendance corrections review` показывает: сотрудник, день, было (Workly), предложено, источник, confidence.
Пока не принято — в итог не входит. Это защита от ошибок распознавания.
EOF

cat > docs/user/03_WRITEBACK.md <<'EOF'
# Возврат правок в Workly (write-back)

## Что можно и чего нельзя
Workly умеет ТОЛЬКО добавлять события. Удалить или изменить отправленное нельзя.
День считается по парам событий, поэтому вставками можно и достроить, и «закрыть» интервал раньше.
Лишнее событие поглощается парой длительностью 1 секунда.

## Порядок (обязательный)
1. Месяц собран, проверки зелёные, руководитель утвердил.
2. `attendance writeback --month YYYY-MM --dry-run` → план: какие события, зачем, ожидаемый эффект по дням.
3. Изучить план. Особое внимание: события на границах месяца и синтез.
4. `attendance writeback --month YYYY-MM --confirm` → отправка + контрольная выгрузка + сверка.
5. Журнал: data/ledger/writeback_YYYY-MM.csv (+ копия на Диск). В Workly все они mode=manual.

## Синтез (R9)
Пушить разрешено, но ПОСЛЕДНИМ и только после финального утверждения суммы:
если сумма изменится, убрать события будет нельзя — только добавить.

## Если день не сошёлся после push
В отчёте появится «не достигнуто». Повторные попытки автоматически не делаются.
Разбираем вручную: смотрим цепочку событий, при необходимости просим вендора удалить лишнее.

## Безопасность
Никогда не запускать --confirm в автоматическом ночном прогоне.
Перед первым боевым применением — эксперимент на тестовом сотруднике («ТЕСТ Табель»).
EOF

cat > docs/user/04_TROUBLESHOOTING.md <<'EOF'
# Частые проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| 401 / code 7008, 7009 | токен истёк/неверный | `attendance probe` обновит токен; проверить .env |
| 403 | роль не администратор | использовать учётку с ролью «Администратор» |
| 429 / code 6000 | превышен лимит (1000/мин) | программа сама делает backoff; не запускать параллельно |
| П1 FAIL | строки не сходятся с итогом Workly | сверить, не менялся ли месяц в Workly после pull; сделать повторный pull |
| П4 FAIL | отработано ≠ уход − приход | проверить правки с ручным hours; пересчитать через recon_* |
| Сотрудник не найден | имя в скане не совпало с ростером | добавить алиас в ростер или указать employee_id |
| Пропуски дней в отчёте | нет данных ни в одном источнике | не выдумывать: очередь подтверждения / запрос сотруднику |
| xlsx «поехал» | merged-ячейки | использовать API; xlsx только как fallback |
| Диск D: недоступен | не смонтирован | `ls /mnt/d` ; при необходимости `sudo mount -t drvfs D: /mnt/d` |
EOF

cat > docs/ARCHITECTURE.md <<'EOF'
# Архитектура (кратко)

Workly API → ingest (JSON, пагинация, throttle) → store SQLite (events_raw, day_frame, employees)
→ rules R1–R9 (чистые функции + audit) → merge с corrections/decisions → checks П1–П5
→ report (CSV/XLSX/PDF) → [опц.] writeback (планировщик пар, dry-run, ledger).

Слои: ingest/ (api + xlsx fallback + recognized), store/, rules/, merge.py, checks.py, report/, writeback/, cli.py.
Принципы: raw неизменяем; каждая правка с источником; правила детерминированы; FAIL = стоп; LLM не считает.
Подробности: context/00_PROJECT.md, context/02_API_DATA.md, docs/DECISIONS.md.
EOF

if ! grep -q '^context-export:' Makefile 2>/dev/null; then
  printf '\ncontext-export:\n\t.venv/bin/python tools/export_context.py\n' >> Makefile
fi

echo "Готово: context/ docs/ data/ out/ созданы, файлы записаны."

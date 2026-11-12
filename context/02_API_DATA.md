# API и контракты данных (актуально на 12.11.2026)

## Эндпоинты
GET  /v1/accounts                        профиль, settings.time_zone
GET  /v1/employees?page&f&fv&ids         id, tab_number, pin_code, full_name, department, schedule, start_date
GET  /v1/employees/dismissed             уволенные (limit ≤100)
GET  /v1/employees/{id}                  карточка
POST /v1/employees                       создать: first_name*, department_id*, locations*, schedule_id*, start_date*, schedule_start_date*; username=email → инвайт
PUT  /v1/employees/{id}                  редактировать (в т.ч. назначить username/должность)
POST /v1/sign-in/password-reset          письмо для задания пароля (пароль через API не задать)
GET  /v1/departments | /locations | /schedules
GET  /v1/reports/inouts?start_date&end_date&f&ids&page   СЫРЬЁ (auto + manual)
GET  /v1/reports/t12?start_date&end_date&f&ids&page      КАРКАС: days[] report_date, is_work_day, is_holiday, work_time, absence_*
GET  /v1/reports/night | /absence        night — только «свободный+» (83359 без нормы пока отдаёт ошибку)
POST /v1/times/clockin | /clockout       {location_id*, employee_id, event_time "Y-m-d H:i:s", latitude, longitude, ip}
DELETE события — нет и не планируют; удаление только в веб-интерфейсе.

## Поля inouts
employee_id, tab_number, pin_code, department_id/title, position_title, event_date,
event_full_date (datetime, сек), event_time, event_code (0=in, 1=out), event_name,
mode (auto|manual), location_id/title, serial_number, photos.

## Модель расчёта дня (подтверждена экспериментом 11.11.2026 и вендором 12.11.2026)
Сумма длительностей пар in→out, «ПОСЛЕДНИЙ приход побеждает»: повторный in без out отбрасывает предыдущий in.
Out без открытого in — сирота, игнорируется. In без out в конце — unclosed.
В колонках «Приход»/«Уход» — ПЕРВЫЙ приход и ПОСЛЕДНИЙ уход дня; на мультипарах отработано ≠ уход−приход.
Доказательство: тестовый 163167, 11.11, 8 событий → 06:10; после удаления 09:50 → 08:00.
Предел пары для «Свободный+» = 28 часов (лимит вендора): приход закрывается первым уходом в пределах 28 ч,
пара относится к дате прихода. День без событий = нулевой (Выходной), расхождением не считается.

## Дефект t12.work_time — ПОДТВЕРЖДЁН ВЕНДОРОМ
Удвоение для графиков «Свободный+» с заданным временем (у нас 08:00–20:00).
Затронуты: t12, /v1/accounts (actual.work_time), /v1/reports, /v1/reports/all-reports.
Фикс до 16.11.2026; после фикса повторный запрос за прошлый период вернёт верные значения.
До фикса верный факт = day_time + night_time из /v1/reports/night.
РЕШЕНИЕ: часы считаем из events_raw; t12 — только календарь. Сторож-тест в tests/test_t12_watchdog.py.

## Ответ вендора (12.11.2026) по прочим вопросам
- Норма для 83359 не задана → задать в день или неделю (месячная для «свободный+» не поддерживается);
  до этого всё уходит в overtime. Overtime до фикса считать самим: work_time_sum − production_time_sum.
- t12 не показывает сотрудника без должности (тестовый 163167) — баг, исправят; назначить должность.
- Уволенные в t12 за прошлые периоды пока не попадают — исправят.
- Пустой _meta: [] — баг, исправят в том же релизе (будет объект с totalCount: 0). get_all уже нормализует.
- /v1/schedules type — объект {id,title}; «Свободный+» = 8. Если придёт число — баг.

## Формат ответов при пустой выборке
"_meta": [] (PHP-массив) вместо объекта; items иногда ассоциативный массив.
get_all нормализует: items dict → values; _meta не dict → стоп после первой страницы.

## Справочники (roster-sync 11.11.2026)
Отделы: 35064 «Отдел по умолчанию» (админ/тестовый), 35065 «Широкоформатная печать» → wide, 35066 «Полиграфия» → offset.
Графики: 80266 по умолчанию; 80267 ШФ 9-19; 80268 свободный 9-19; 80269/80270 Полиграфия 8-20 (+смены);
81868 ШФ 9-19 (свободный+, type 8); 83359 Полиграфия 8-20 (свободный+, тип 8).
Базовые смены для реконструкции: офсет 08:00–20:00 (12 ч), ШФ 09:00–19:00 (10 ч).
Локация 29384 «Локация по умолчанию». Админ 134300 — exclude=1.
Тестовый 163167 «Табель ТЕСТ» (dept 35064, schedule 83359) — удалить после экспериментов.
Нормализация имён обязательна: " ".join(name.split()) + resolve_name() (Workly даёт пробелы).

## Слои данных (актуальная модель)
Итог = AUTO (API inouts) + MANUAL (наш corrections-реестр). Скрытого ручного слоя в Workly нет.
Расхождения старого октябрьского xlsx с API объяснены устаревшими/поправленными значениями; свежий экспорт совпал с API.
Возможны строки в утверждённом табеле без метки и без событий в API (ручной ввод при создании табеля) — см. приёмку октября.

## Контракт правок corrections.json (v1)
{version, month, source:{kind:scan|manual|paper|decision, id, file},
entries:[{employee_raw, employee_id?, day, cin?, cout?, hours?, action, confidence, note, pushable}],
low_confidence:[{ref, reason, candidates}]}
action: set|add|recon_logout|recon_login|keep|glitch|dayoff|vacation|synth_r9. worked считает Python.
scans.json — распечатки/блокноты; paper.json — матрица офсета (только часы).

## Итоговый табель (утверждённый формат)
CSV «;» UTF-8 (без BOM). Шапка: Сотрудник / Итого;Дата;Неделя;Приход;Уход;Отработано;Метка
Блок: ФИО → все дни месяца (DD.MM.YYYY, пон/втор/сред/чет/пят/суб/вос) → строка «Итого;;;;;<сумма>;».
Порядок сотрудников — employees.sort_order (заполняется из эталона). Состояния: Выходной, Отпуск. Время HH:MM.

## Планировщик write-back
1 цепочка событий за месяц ±1 день → 2 симуляция пар (last-in-wins) → 3 сравнение с утверждённым табелем
→ 4 минимальные вставки (нет out: +out; нет in: +in; бродячий out: +in за 1 с до; бродячий in: +out через 1 с после)
→ 5 пересимуляция → 6 dry-run → confirm → POST → контрольный pull.
Ledger: data/ledger/*.jsonl + копия на Диск. Откат — удаление в веб-UI по ledger.

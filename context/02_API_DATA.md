# API и контракты данных (актуально на 11.11.2026)

## Эндпоинты
GET  /v1/accounts                         профиль, settings.time_zone
GET  /v1/employees?page&f&fv&ids          id, tab_number, pin_code, full_name, department, schedule, start_date
GET  /v1/employees/dismissed              уволенные (limit ≤100)
GET  /v1/employees/{id}                   карточка
POST /v1/employees                        создать: first_name*, department_id*, locations*, schedule_id*, start_date*, schedule_start_date*; username=email
POST /v1/sign-in/password-reset           письмо для задания пароля (пароль через API не задать)
GET  /v1/departments | /locations | /schedules
GET  /v1/reports/inouts?start_date&end_date&f&ids&page   СЫРЬЁ (auto + manual)
GET  /v1/reports/t12?start_date&end_date&f&ids&page      КАРКАС: days[] report_date, is_work_day, is_holiday, work_time, absence_*
GET  /v1/reports/night | /absence         night — только графики «свободный+»
POST /v1/times/clockin | /clockout        {location_id*, employee_id, event_time "Y-m-d H:i:s", latitude, longitude, ip}
Редактирование/увольнение/восстановление/удаление уволенного/массовое добавление — разделы доки есть, точные URL уточняем probe.
DELETE события — в доке нет; в веб-UI удаление работает. Запрос вендору: есть ли DELETE /v1/times/{id}.

## Поля inouts
employee_id, tab_number, pin_code, department_id/title, position_title, event_date,
event_full_date (datetime, сек), event_time, event_code (0=in, 1=out), event_name,
mode (auto|manual), location_id/title, serial_number, photos.

## Модель расчёта дня (ПОДТВЕРЖДЕНА экспериментом 11.11.2026)
Сумма длительностей пар in→out, правило «ПОСЛЕДНИЙ приход побеждает»:
повторный in без промежуточного out отбрасывает предыдущий in.
Out без открытого in — сирота, игнорируется. In без out в конце — unclosed.
В колонках «Приход»/«Уход» отображаются ПЕРВЫЙ приход и ПОСЛЕДНИЙ уход дня,
поэтому на мультипарных днях отработано ≠ уход − приход.
Доказательство: тестовый 163167, 11.11, 8 событий → веб-сводная 06:10
(09:50→12:00 = 2:10; 13:00→17:00 = 4:00; 18:09:59→18:10 = 1 с; out 18:00 — сирота).
После удаления 09:50 ожидается 08:00. Предел пары max_pair_min = 26 ч.
День без событий = нулевой день (Выходной), расхождением не считается.

## Дефект t12.work_time
t12.work_time = 2 × реальное время (±1 мин от секунд). 322/322 ненулевых дней сентября.
Пример: Альфредо 160237, 14.09 события 07:46:40→19:52:33 = 12:05:53, xlsx 725 мин, API 1451 мин.
РЕШЕНИЕ: часы считать из events_raw; t12 — только календарь (is_work_day, is_holiday, absence, worked_days).
Тикет вендору отправлен.

## Формат ответов при пустой выборке
"_meta": [] (PHP-массив) вместо объекта; items иногда ассоциативный массив.
get_all нормализует: items dict → values; _meta не dict → стоп после первой страницы.

## Справочники (roster-sync 11.11.2026)
Отделы: 35064 «Отдел по умолчанию» (админ/тестовый), 35065 «Широкоформатная печать» → wide,
35066 «Полиграфия» → offset. Цех выводится из department_id.
Графики: 80266 по умолчанию; 80267 ШФ 9-19; 80268 свободный 9-19; 80269/80270 Полиграфия 8-20 (+смены);
81868 ШФ 9-19 (свободный+); 83359 Полиграфия 8-20 (свободный+). /schedules не отдаёт type.
Базовые смены для реконструкции: офсет 08:00–20:00 (12 ч), ШФ 09:00–19:00 (10 ч).
Локация 29384 «Локация по умолчанию». Админ 134300 — exclude=1.
Тестовый 163167 «Табель ТЕСТ» (dept 35064, schedule 83359) — удалить после экспериментов.
Нормализация имён обязательна: " ".join(name.split()) + resolve_name() (Workly даёт пробелы).

## Слои данных (актуальная модель)
API inouts отдаёт и auto, и manual (наши pushes видны). Скрытого ручного слоя НЕТ.
Расхождения старого октябрьского xlsx с API объяснены устаревшими/поправленными значениями;
свежий экспорт совпал с API. Итог = AUTO (API) + MANUAL (наш corrections-реестр).
t12 за текущий день по тестовому = 0 записей (отдел 35064 либо ночной пересчёт) — уточняется.

## Контракт правок corrections.json (v1)
{version, month, source:{kind:scan|manual|paper|decision, id, file},
 entries:[{employee_raw, employee_id?, day, cin?, cout?, hours?, action, confidence, note, pushable}],
 low_confidence:[{ref, reason, candidates}]}
action: set|add|recon_logout|recon_login|keep|glitch|dayoff|vacation|synth_r9. worked считает Python.
scans.json — распечатки/блокноты; paper.json — матрица офсета (только часы).

## Итоговый табель (утверждённый формат)
CSV «;» UTF-8. Шапка: Сотрудник / Итого;Дата;Неделя;Приход;Уход;Отработано;Метка
Блок: ФИО → все дни месяца (DD.MM.YYYY, пон/втор/сред/чет/пят/суб/вос) → «Итого».
Состояния: Выходной, Отпуск. Время HH:MM, итог ЧЧ:ММ (>24 ч допустимо).

## Планировщик write-back
1 цепочка событий за месяц ±1 день → 2 симуляция пар (last-in-wins) → 3 сравнение с утверждённым табелем
→ 4 минимальные вставки (нет out: +out; нет in: +in; бродячий out: +in за 1 с до; бродячий in: +out через 1 с после)
→ 5 пересимуляция → 6 dry-run → confirm → POST → контрольный pull.
Ledger: data/ledger/*.jsonl + копия на Диск. Откат — удаление в веб-UI по ledger.

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

## Справочники Workly (проверено 11.11.2026, roster-sync)
Отделы: 35064 «Отдел по умолчанию» (админ/новые), 35065 «Широкоформатная печать» → wide,
35066 «Полиграфия» → offset. Цех выводится из department_id, ручная разметка — только для 35064.
Графики: 80266 по умолчанию; 80267 ШФ 9-19; 80268 свободный 9-19;
80269/80270 Полиграфия 8-20 (+смены); 81868 ШФ 9-19 (свободный+); 83359 Полиграфия 8-20 (свободный+).
Базовые смены для реконструкции: офсет 08:00–20:00 (12 ч), ШФ 09:00–19:00 (10 ч).
/reports/night доступен только для графиков «свободный+» (81868, 83359).
Список /schedules не отдаёт type (None) — при необходимости брать из карточки графика.

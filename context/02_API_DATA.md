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

## Нормализация имён (обязательно)
Workly full_name содержит ведущие/хвостовые пробелы (пустые last_name/patronymic):
" Альфредо ", "Аринаркина Ольга ". Перед любым сопоставлением: " ".join(name.split())
и resolve_name() из ростера. Иначе ключи (имя, день) не совпадают.
Админ: employee_id 134300 (Аксёнов Андрей Александрович), dept 35064, exclude=1.
Цеха подтверждены данными: 35066 → offset (13 чел.), 35065 → wide (11 чел., включая Горбатова).

## Осторожно: t12.work_time
В выгрузке сентября значения ~1440 мин (24 ч) на обычный день и 2875 мин (47:55) на 23.09.
До проверки сырого JSON НЕ использовать t12.work_time как источник часов.
ПОДТВЕРЖДЕНО: t12.work_time = 2 × реальное время (±1 мин от секунд).
Пример: Альфредо (160237) 14.09 события 07:46:40→19:52:33 = 12:05:53,
xlsx 725 мин, API 1451 мин; сумма сентября xlsx 180:12, API 360:25.
РЕШЕНИЕ: часы считать из events_raw по модели пар (in→out), смена по дате прихода;
t12 использовать только как календарь (is_work_day, is_holiday, absence, worked_days).
Сироты (out без in, in без out) помечаются и обрабатываются правилами R1–R9.

## Подтверждение дефекта t12 (11.11.2026)
322 из 322 ненулевых дней сентября: API = 2 × веб-экспорт (±1 мин), исключений 0.
Тикет вендору подготовлен (пример: employee_id 160237, 14.09, 12:05:53 → API 24:11).

## Модель пар: ограничения
Предел длительности пары max_pair_min = 26 ч (пропускает реальные 24:23, отсекает склейку через выходные). Пары длиннее — unclosed_in + orphan_out.
День без событий эквивалентен нулевому дню (Выходной) — расхождением не считается.

## Проверка модели пар (11.11.2026)
Сентябрь: 342 дня, расхождений с веб-экспортом 0. Октябрь: 428 дней, 3 расхождения
(Шумиков 04/05/25 — дни ручных правок). Гипотеза: /reports/inouts не возвращает
события mode=manual. Если подтвердится — write-back проверяем повторным веб-экспортом,
а не через inouts.

## Ограничение /reports/inouts (подтверждено 11.11.2026)
Возвращает ТОЛЬКО события mode=auto. За октябрь 838/838 событий auto, ни одного manual.
Ручные отметки, внесённые через веб-интерфейс Workly, в эндпоинт не попадают.
Доказательство: Шумиков (135223) 04.10 — веб-экспорт 08:00–19:40/11:40, в API событий нет;
05.10 — в API только out 19:59:48 (orphan_out); 25.10 — только in 07:33:55 (unclosed_in).
Контрольный день 24.10 (оба события auto) совпал поминутно: 758 мин.
Следствие: слой MANUAL ведём мы (corrections-реестр). Итог = AUTO (API) + MANUAL (наш реестр).
Write-back НЕ проверяется через inouts: только ledger + t12÷2 (если t12 видит manual) + веб-экспорт.
Сентябрь: 0 расхождений (ручных правок в Workly не было). Октябрь: 3 расхождения = 3 ручных дня.

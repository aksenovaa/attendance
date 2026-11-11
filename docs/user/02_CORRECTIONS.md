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

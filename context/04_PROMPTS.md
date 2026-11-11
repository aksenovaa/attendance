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

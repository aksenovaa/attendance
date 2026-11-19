"""П5: формат утверждённого табеля."""

from __future__ import annotations

from pathlib import Path

from attendance.checks_p5 import check5

GOOD = (
    "Сотрудник / Итого;Дата;Неделя;Приход;Уход;Отработано;Метка\n"
    "Альфредо;;;;;;\n"
    ";01.10.2026;чет;08:00;19:58;11:58;\n"
    ";03.10.2026;суб;Выходной;;;Выходной\n"
    "Итого;;;;;11:58;\n"
)


def test_good_format(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text(GOOD, encoding="utf-8")
    assert check5(p) == []


def test_bad_time_and_tag(tmp_path: Path) -> None:
    bad = GOOD.replace("08:00", "8:0").replace("11:58;\n;03", "11:58;неизвестно\n;03")
    p = tmp_path / "t.csv"
    p.write_text(bad, encoding="utf-8")
    issues = check5(p)
    assert any("приход" in i for i in issues)
    assert any("метка" in i for i in issues)


def test_missing_total(tmp_path: Path) -> None:
    no_total = GOOD.replace("Итого;;;;;11:58;\n", "")
    p = tmp_path / "t.csv"
    p.write_text(no_total, encoding="utf-8")
    assert any("Итого" in i for i in check5(p))

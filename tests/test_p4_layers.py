"""П4 по слоям: AUTO — FAIL по span; правки — WARN по отображаемым временам."""

from __future__ import annotations

from attendance.checks_p4 import check4_edited, check4_rows
from attendance.merge import FinalRow


def _row(
    source: str = "api",
    worked: int | None = 600,
    span: int | None = 600,
    pairs: int = 1,
    cin: int | None = 480,
    cout: int | None = 1080,
    state: str = "",
) -> FinalRow:
    return FinalRow(
        employee_id=1,
        day=1,
        cin=cin,
        cout=cout,
        worked=worked,
        state=state,
        tag="",
        source=source,
        pairs=pairs,
        span=span,
    )


def test_auto_single_exact_passes() -> None:
    assert check4_rows([_row()]) == []


def test_auto_single_mismatch_fails() -> None:
    issues = check4_rows([_row(worked=601)])
    assert len(issues) == 1
    assert issues[0].layer == "auto"


def test_auto_no_span_fails() -> None:
    issues = check4_rows([_row(span=None)])
    assert len(issues) == 1
    assert issues[0].kind == "нет span"


def test_edited_not_checked_by_p4a() -> None:
    assert check4_rows([_row(source="scan", span=None)]) == []


def test_edited_consistent_no_warn() -> None:
    assert check4_edited([_row(source="scan")]) == []


def test_edited_off_by_one_no_warn() -> None:
    assert check4_edited([_row(source="scan", worked=599)]) == []


def test_edited_inconsistent_warns() -> None:
    issues = check4_edited([_row(source="scan", worked=100)])
    assert len(issues) == 1
    assert issues[0].layer == "edited"


def test_state_days_skipped() -> None:
    assert check4_rows([_row(state="Отпуск")]) == []
    assert check4_edited([_row(state="Отпуск", source="scan")]) == []


def test_auto_discarded_in_passes_bound() -> None:
    # отброшенный ранний in: span шире отработанного — это норма, не FAIL
    row = _row(source="api", cin=360, worked=660, span=720, pairs=1)
    assert check4_rows([row]) == []


def test_auto_over_span_fails() -> None:
    row = _row(source="api", worked=800, span=720, pairs=1)
    issues = check4_rows([row])
    assert len(issues) == 1
    assert issues[0].layer == "auto"

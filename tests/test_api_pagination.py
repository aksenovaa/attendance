"""Пагинация get_all: склеивает страницы и останавливается по pageCount."""

from __future__ import annotations

from typing import Any

from attendance.config import Settings
from attendance.ingest.workly_api import WorklyClient


def _settings(tmp_path: Any) -> Settings:
    return Settings("id", "secret", "user", "pass", data_dir=tmp_path)


def test_get_all_pages(tmp_path: Any, monkeypatch: Any) -> None:
    client = WorklyClient(_settings(tmp_path))
    pages = {
        1: {"items": [{"id": 1}], "_meta": {"pageCount": 2}},
        2: {"items": [{"id": 2}], "_meta": {"pageCount": 2}},
    }

    def fake_get(path: str, **params: Any) -> dict[str, Any]:
        return pages[int(params["page"])]

    monkeypatch.setattr(client, "get", fake_get)
    assert [x["id"] for x in client.get_all("employees")] == [1, 2]


def test_get_all_meta_is_list(tmp_path: Any, monkeypatch: Any) -> None:
    client = WorklyClient(_settings(tmp_path))

    def fake_get(path: str, **params: Any) -> dict[str, Any]:
        return {"items": [], "_meta": []}

    monkeypatch.setattr(client, "get", fake_get)
    assert client.get_all("reports/t12") == []


def test_get_all_items_is_dict(tmp_path: Any, monkeypatch: Any) -> None:
    client = WorklyClient(_settings(tmp_path))

    def fake_get(path: str, **params: Any) -> dict[str, Any]:
        return {"items": {"0": {"id": 7}}, "_meta": {"pageCount": 1}}

    monkeypatch.setattr(client, "get", fake_get)
    assert client.get_all("employees") == [{"id": 7}]

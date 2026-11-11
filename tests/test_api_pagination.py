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

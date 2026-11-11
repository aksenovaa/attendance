"""Клиент Workly API: токен, пагинация, троттлинг, ретраи."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from ..config import Settings


class WorklyError(RuntimeError):
    """Запрос не удался после всех попыток."""


class WorklyClient:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._session = requests.Session()
        self._token: str | None = None
        self._refresh: str | None = None
        self._expires_at = 0.0
        self._min_interval = 1.0 / settings.rps
        self._last_call = 0.0
        self._load_token()

    def _load_token(self) -> None:
        path = self.s.token_path
        if not path.exists():
            return
        data = json.loads(path.read_text("utf-8"))
        self._token = data.get("access_token")
        self._refresh = data.get("refresh_token")
        self._expires_at = float(data.get("expires_at", 0))

    def _save_token(self, data: dict[str, Any]) -> None:
        self._token = data["access_token"]
        self._refresh = data.get("refresh_token")
        self._expires_at = time.time() + float(data.get("expires_in", 0)) - 300
        self.s.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.s.token_path.write_text(
            json.dumps(
                {
                    "access_token": self._token,
                    "refresh_token": self._refresh,
                    "expires_at": self._expires_at,
                }
            ),
            encoding="utf-8",
        )
        self.s.token_path.chmod(0o600)

    def _auth(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._expires_at:
            return self._token
        payload = {
            "client_id": self.s.client_id,
            "client_secret": self.s.client_secret,
        }
        if not force and self._refresh:
            payload["grant_type"] = "refresh_token"
            payload["refresh_token"] = self._refresh
        else:
            payload["grant_type"] = "password"
            payload["username"] = self.s.username
            payload["password"] = self.s.password
        resp = self._session.post(
            f"{self.s.base_url}/oauth/token", data=payload, timeout=self.s.timeout
        )
        if resp.status_code >= 400 and payload["grant_type"] == "refresh_token":
            return self._auth(force=True)
        resp.raise_for_status()
        self._save_token(resp.json())
        if self._token is None:
            raise WorklyError("Пустой access_token")
        return self._token

    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        for attempt in range(5):
            self._throttle()
            token = self._auth()
            resp = self._session.get(
                f"{self.s.base_url}/{path.lstrip('/')}",
                headers={"authorization": f"Bearer {token}"},
                params=params,
                timeout=self.s.timeout,
            )
            if resp.status_code == 401 and attempt == 0:
                self._auth(force=True)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(min(2**attempt, 30))
                continue
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
        raise WorklyError(f"GET {path}: не удалось за 5 попыток")

    def get_all(self, path: str, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self.get(path, page=page, **params)
            items.extend(payload.get("items", []))
            meta = payload.get("_meta", {})
            if page >= int(meta.get("pageCount", 1) or 1):
                break
            page += 1
        return items

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        token = self._auth()
        resp = self._session.post(
            f"{self.s.base_url}/{path.lstrip('/')}",
            headers={
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
            },
            json=payload,
            timeout=self.s.timeout,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

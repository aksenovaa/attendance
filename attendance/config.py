"""Настройки: секреты только из .env, пути — от корня репозитория."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    username: str
    password: str
    base_url: str = "https://api.workly.io/v1"
    tz: str = "Europe/Moscow"
    rps: float = 8.0
    timeout: int = 30
    data_dir: Path = ROOT / "data"
    out_dir: Path = ROOT / "out"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "attendance.sqlite"

    @property
    def token_path(self) -> Path:
        return self.data_dir / ".workly_token.json"


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    keys = (
        "WORKLY_CLIENT_ID",
        "WORKLY_CLIENT_SECRET",
        "WORKLY_USERNAME",
        "WORKLY_PASSWORD",
    )
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise SystemExit(f"В .env не заданы: {', '.join(missing)}")
    return Settings(
        client_id=os.environ["WORKLY_CLIENT_ID"],
        client_secret=os.environ["WORKLY_CLIENT_SECRET"],
        username=os.environ["WORKLY_USERNAME"],
        password=os.environ["WORKLY_PASSWORD"],
        rps=float(os.getenv("WORKLY_RPS") or 8.0),
    )

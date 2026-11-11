#!/usr/bin/env python3
"""Копирует context/*.md в папку контекста на Яндекс.Диске (Windows через WSL)."""

import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "context"
DEST = Path("/mnt/d/YD/Yandex.Disk/@Работа/сайты/art-poligrafy.ru/Персонал/Контекст")


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEST
    if not dest.parent.exists():
        print(f"Путь недоступен: {dest.parent} (смонтирован ли D:?)")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.md")):
        shutil.copy2(f, dest / f.name)
        print("→", dest / f.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

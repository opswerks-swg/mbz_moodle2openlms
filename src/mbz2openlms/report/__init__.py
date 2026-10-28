"""Markdown and JSON reports. Markdown reports are shareable: they never contain answer keys."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def to_json(data: Any) -> str:
    def default(value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (Path, set)):
            return str(value) if isinstance(value, Path) else sorted(value)
        raise TypeError(type(value))

    if dataclasses.is_dataclass(data):
        data = dataclasses.asdict(data)
    return json.dumps(data, indent=2, ensure_ascii=False, default=default) + "\n"


def cell(value: Any) -> str:
    """A Markdown table cell."""
    return " ".join(str(value if value is not None else "").split()).replace("|", "\\|")


def table(header: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return lines + [""]


def date(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else ""

"""Session list payload helpers."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def session_items(entries: Iterable[Any], title_for: Callable[[str], str | None]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        item = slim_session(entry, title_for)
        existing = by_id.get(item["id"])
        if existing is None or item["updated"] > existing["updated"]:
            by_id[item["id"]] = item
    return sorted(by_id.values(), key=lambda item: item["updated"], reverse=True)


def slim_session(entry: Any, title_for: Callable[[str], str | None]) -> dict[str, Any]:
    session_id = entry.session_id
    display_name = entry.display_name.strip() if isinstance(entry.display_name, str) else None
    return {
        "id": session_id,
        "title": title_for(session_id) or display_name or "New session",
        "updated": entry.updated_at.timestamp() if entry.updated_at else 0,
        "tokens": (entry.input_tokens or 0) + (entry.output_tokens or 0),
    }

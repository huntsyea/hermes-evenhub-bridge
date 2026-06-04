"""Session list payload helpers."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any


def session_items(
    entries: Iterable[Any],
    title_for: Callable[[str], str | None],
    rich_sessions: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rich_sessions:
        item = slim_rich_session(row)
        if item is not None:
            by_id[item["id"]] = item
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


def slim_rich_session(row: Mapping[str, Any]) -> dict[str, Any] | None:
    session_id = row.get("id")
    if not isinstance(session_id, str) or not session_id:
        return None
    title = row.get("title")
    preview = row.get("preview")
    return {
        "id": session_id,
        "title": _clean_text(title) or _clean_text(preview) or "New session",
        "updated": _float_value(row.get("last_active")) or _float_value(row.get("started_at")),
        "tokens": _int_value(row.get("input_tokens")) + _int_value(row.get("output_tokens")),
    }


def _clean_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _float_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _int_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 0

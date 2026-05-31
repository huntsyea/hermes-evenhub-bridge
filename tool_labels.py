"""Small labels for tool activity displayed on glasses."""
from __future__ import annotations

import json
from typing import Any

TOOL_LABEL_MAX_CHARS = 64


def tool_label(tool_name: str, args: Any, *, max_chars: int = TOOL_LABEL_MAX_CHARS) -> str:
    detail = _tool_detail(args)
    if not detail:
        return tool_name
    return _truncate_label(f"{tool_name}: {detail}", max_chars)


def _tool_detail(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return _one_line(args)
    if not isinstance(args, dict):
        return ""

    for key in ("command", "cmd", "query", "path", "file_path", "url", "tool_name"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return _one_line(value)

    for key in ("paths", "files"):
        value = args.get(key)
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value[:2])
            if text:
                return _one_line(text)
    return ""


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _truncate_label(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."

"""Global pre/post tool-call hooks that emit structured tool frames to the
connected glasses whose active session matches the hook's session_id.

Hooks can fire from the agent's worker thread, so frame sends are scheduled
onto the adapter's event loop via run_coroutine_threadsafe."""
from __future__ import annotations

import asyncio
import logging

from . import protocol as P

log = logging.getLogger("hermes-evenhub-bridge")
_adapter = None


def bind(adapter) -> None:
    # One adapter per gateway process; a second bind() replaces the first.
    global _adapter
    _adapter = adapter


def _chat_for_session(session_id: str):
    if _adapter is None or not session_id:
        return None
    for chat_id, sid in _adapter._session_by_chat.items():
        if sid == session_id and _adapter._registry.is_connected(chat_id):
            return chat_id
    return None


def _emit(chat_id: str, frame: str) -> None:
    loop = getattr(_adapter, "_loop", None)
    if loop is None or not loop.is_running():
        # No running adapter loop to schedule onto; drop rather than risk
        # scheduling on the wrong/closed loop from a worker thread.
        log.debug("hooks._emit: adapter loop not ready, dropping frame for %s", chat_id)
        return
    fut = asyncio.run_coroutine_threadsafe(
        _adapter._registry.send_frame(chat_id, frame), loop)

    def _log(f):
        try:
            exc = f.exception()
        except Exception:
            return
        if exc:
            log.debug("hooks: send_frame error for %s: %s", chat_id, exc)

    fut.add_done_callback(_log)


def pre_tool_call(*, tool_name, args, task_id, session_id, tool_call_id, **_):
    chat_id = _chat_for_session(session_id)
    if chat_id:
        _emit(chat_id, P.tool_start(tool_name))
    return None


def post_tool_call(*, tool_name, args, result, task_id, session_id, tool_call_id,
                   duration_ms=0, **_):
    chat_id = _chat_for_session(session_id)
    if chat_id:
        # TODO: inspect `result` to signal tool errors (ok=False); v1 always ok.
        _emit(chat_id, P.tool_end(tool_name, ok=True))
    return None

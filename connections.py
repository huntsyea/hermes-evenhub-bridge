"""Connection registry: maps a glasses chat_id to its live WebSocket and the
per-chat streaming state used to convert accumulated gateway text into the
glasses' delta wire-protocol."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

log = logging.getLogger("hermes-evenhub-bridge")

# The gateway's GatewayStreamConsumer appends this cursor to in-progress
# streaming frames (gateway/config.py: DEFAULT_STREAMING_CURSOR = " ▉") and
# removes it on the finalize edit. We strip the EXACT cursor string (not
# rstrip) so legitimate trailing spaces in the model's text are preserved.
# Verified empirically by the Task 0 spike against the real consumer.
STREAMING_CURSOR = " ▉"


@dataclass
class StreamState:
    """Tracks how much accumulated assistant text has already been sent to the
    glasses as deltas for the current message segment. Gateway frames carry a
    trailing streaming cursor that must be stripped before diffing."""
    sent_len: int = 0

    def delta_for(self, accumulated: str) -> str:
        """Return the unsent suffix of ``accumulated`` (cursor stripped) and
        advance the marker."""
        clean = accumulated
        if clean.endswith(STREAMING_CURSOR):
            clean = clean[: -len(STREAMING_CURSOR)]
        if len(clean) < self.sent_len:
            # Content shrank (new segment reusing the buffer): treat as fresh.
            self.sent_len = 0
        delta = clean[self.sent_len:]
        self.sent_len = len(clean)
        return delta

    def reset(self) -> None:
        self.sent_len = 0


class ConnectionRegistry:
    def __init__(self) -> None:
        self._ws: Dict[str, Any] = {}
        self._state: Dict[str, StreamState] = {}

    def register(self, chat_id: str, ws: Any) -> None:
        self._ws[chat_id] = ws
        self._state[chat_id] = StreamState()

    def unregister(self, chat_id: str, ws: Any = None) -> None:
        # Guard the reconnect race: a stale connection's teardown must not drop
        # a newer connection that reused the same chat_id. Only remove when the
        # stored socket matches (or when no ws is supplied, e.g. explicit teardown).
        if ws is not None and self._ws.get(chat_id) is not ws:
            return
        self._ws.pop(chat_id, None)
        self._state.pop(chat_id, None)

    def is_connected(self, chat_id: str) -> bool:
        return chat_id in self._ws

    def count(self) -> int:
        return len(self._ws)

    def chat_ids(self) -> list[str]:
        return list(self._ws)

    def stream_state(self, chat_id: str) -> StreamState:
        return self._state.setdefault(chat_id, StreamState())

    async def send_frame(self, chat_id: str, frame: str) -> None:
        ws = self._ws.get(chat_id)
        if ws is None:
            log.debug("send_frame: no socket for %s", chat_id)
            return
        try:
            await ws.send(frame)
        except Exception as e:  # connection dropped mid-send
            log.debug("send_frame failed for %s: %s", chat_id, e)
            self.unregister(chat_id, ws)

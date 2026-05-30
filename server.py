"""WebSocket transport for the G2 bridge. Authenticates the hello handshake,
registers the connection, buffers PCM during audio.start/stop, and routes
client frames to the adapter. Streaming OUT is push-driven by the adapter via
the ConnectionRegistry, not pulled here."""
from __future__ import annotations

import contextlib
import hmac
import logging
import os

import websockets

from . import protocol as P
from .config import BridgeConfig
from .connections import ConnectionRegistry

log = logging.getLogger("hermes-evenhub-bridge")

# Cap buffered PCM per audio.start stream so an authenticated client can't OOM the
# gateway by flooding binary frames. ~8 MiB ≈ 4 min of 16 kHz mono 16-bit PCM.
# Override via EVENHUB_MAX_PCM_BYTES (also lets tests use a tiny cap).
_MAX_PCM_BYTES = int(os.environ.get("EVENHUB_MAX_PCM_BYTES", 8 * 1024 * 1024))


class BridgeServer:
    def __init__(self, cfg: BridgeConfig, registry: ConnectionRegistry, adapter) -> None:
        self._cfg = cfg
        self._registry = registry
        self._adapter = adapter
        self._server = None
        self.port = 0

    async def start(self, bind_host: str | None = None) -> int:
        if not self._cfg.token:
            log.warning(
                "EVENHUB_BRIDGE_TOKEN is empty; the G2 bridge will reject all "
                "connections until a pairing token is configured")
        self._server = await websockets.serve(
            self._handle, bind_host or self._cfg.ws_host, self._cfg.ws_port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, ws, *args):
        try:
            hello = P.parse_client(await ws.recv())
        except Exception:
            with contextlib.suppress(Exception):
                await ws.close(code=1008, reason="bad hello")
            return
        # An empty configured token means no pairing secret is set -> refuse all.
        # Constant-time compare so the token isn't probeable via response timing.
        client_tok = hello.get("token")
        authed = (
            bool(self._cfg.token)
            and isinstance(client_tok, str)
            and hmac.compare_digest(client_tok, self._cfg.token)
        )
        if hello.get("t") != "hello" or not authed:
            with contextlib.suppress(Exception):
                await ws.close(code=1008, reason="unauthorized")
            return
        chat_id = hello.get("device") or "g2"
        self._registry.register(chat_id, ws)
        self._adapter.refresh_status()
        try:
            await ws.send(P.hello_ok(active=self._adapter_active(chat_id)))
            pcm: bytearray | None = None
            async for raw in ws:
                if isinstance(raw, (bytes, bytearray)):
                    if pcm is not None:
                        if len(pcm) + len(raw) > _MAX_PCM_BYTES:
                            # Overflow: drop the stream rather than buffer unbounded.
                            pcm = None
                            await ws.send(P.error("audio stream too large"))
                        else:
                            pcm.extend(raw)
                    continue
                try:
                    msg = P.parse_client(raw)
                except ValueError:
                    await ws.send(P.error("bad message"))
                    continue
                t = msg["t"]
                if t == "audio.start":
                    pcm = bytearray()
                    continue
                # Snapshot + clear the buffer BEFORE dispatch so a failing
                # on_audio can't cause the bytes to be re-delivered on retry.
                snapshot = None
                if t == "audio.stop":
                    snapshot = bytes(pcm) if pcm is not None else b""
                    pcm = None
                try:
                    await self._dispatch(ws, chat_id, msg, snapshot)
                except Exception:
                    log.exception("adapter dispatch failed for %s (%s)", chat_id, t)
                    await ws.send(P.error("internal error"))
        finally:
            self._registry.unregister(chat_id, ws)
            self._adapter.refresh_status()

    async def _dispatch(self, ws, chat_id, msg, snapshot):
        """Route one client frame to the adapter. PCM lifecycle is managed by
        the caller; ``snapshot`` holds the captured audio bytes for audio.stop."""
        t = msg["t"]
        if t == "audio.stop":
            await self._adapter.on_audio(chat_id, snapshot or b"")
            return
        if t == "text":
            text = msg.get("text")
            if text is None:
                await ws.send(P.error("bad message"))
            else:
                await self._adapter.on_text(chat_id, text)
        elif t == "sessions.list":
            await self._adapter.on_sessions_list(chat_id)
        elif t == "sessions.switch":
            sid = msg.get("id")
            if not sid:
                await ws.send(P.error("bad message"))
            else:
                await self._adapter.on_sessions_switch(chat_id, sid)
        elif t == "sessions.new":
            await self._adapter.on_sessions_new(chat_id)
        elif t == "stop":
            await self._adapter.on_stop(chat_id)

    def _adapter_active(self, chat_id: str) -> str:
        return getattr(self._adapter, "_session_by_chat", {}).get(chat_id, "")

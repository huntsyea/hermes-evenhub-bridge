"""EvenG2Adapter — a Hermes gateway platform adapter for Even Realities G2
smart glasses. Owns a LAN WebSocket server; bridges glasses <-> the gateway."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult, MessageEvent, MessageType
from gateway.session import build_session_key

from .config import BridgeConfig
from .connections import ConnectionRegistry
from . import protocol as P
from .server import BridgeServer
from .setup_flow import local_bridge_url
from .status import StatusFile
from .session_items import session_items
from .tool_labels import tool_label
from .asr import load_active, resolve_active_name

log = logging.getLogger("hermes-evenhub-bridge")

HISTORY_MAX_ITEMS = 80
HISTORY_MAX_CHARS = 12_000


class EvenG2Adapter(BasePlatformAdapter):
    def __init__(
        self,
        config: PlatformConfig,
        bridge_cfg: BridgeConfig | None = None,
        status_path: Path | None = None,
    ) -> None:
        super().__init__(config, Platform("even_g2"))
        self._bridge_cfg = bridge_cfg or BridgeConfig.from_env()
        self._registry = ConnectionRegistry()
        self._status = StatusFile(status_path)
        self._server = BridgeServer(self._bridge_cfg, self._registry, self)
        # chat_id -> agent session_id, kept current for hook scoping & status.
        self._session_by_chat: Dict[str, str] = {}
        self._loop = None
        self._idle_poll_seconds = 0.1
        self._poller_tasks: dict[str, asyncio.Task] = {}
        self._transcriber = None
        self._active_name = None
        self._suppressed_command_output: dict[str, int] = {}

    @property
    def bound_port(self) -> int:
        return self._server.port

    async def connect(self) -> bool:
        from . import net
        loop = asyncio.get_running_loop()
        # Tailscale detection shells out to the CLI — keep it off the event loop.
        bind, connect_url, ts = await loop.run_in_executor(
            None, net.resolve, self._bridge_cfg)
        await self._server.start(bind)
        try:
            self._loop = loop
            self._mark_connected()
            self._status.update(
                connected=0, mic="off", active_session="",
                connect_url=connect_url,
                public_url=self._bridge_cfg.public_url,
                local_url=local_bridge_url(self._bridge_cfg),
                serve_port=self._bridge_cfg.serve_port,
                tailscale_dns=(ts or {}).get("magic_dns", ""),
                tailscale_ip=(ts or {}).get("ip", ""),
                net_mode=self._bridge_cfg.net_mode,
            )
            log.info("EvenG2 adapter listening on %s:%s — glasses URL: %s",
                     bind, self._server.port, connect_url)
            return True
        except Exception:
            # Don't leave the socket listening if post-start setup fails.
            await self._server.stop()
            self._mark_disconnected()
            raise

    async def disconnect(self) -> None:
        for task in list(self._poller_tasks.values()):
            task.cancel()
        self._poller_tasks.clear()
        await self._server.stop()
        self._mark_disconnected()

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": chat_id, "type": "dm"}

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        if self._is_command_output_suppressed(chat_id):
            return SendResult(success=True, message_id="g2")
        state = self._registry.stream_state(chat_id)
        state.reset()
        delta = state.delta_for(content or "")
        if delta:
            await self._registry.send_frame(chat_id, P.assistant_delta(delta))
        return SendResult(success=True, message_id="g2")

    async def edit_message(self, chat_id, message_id, content, *, finalize=False) -> SendResult:
        if self._is_command_output_suppressed(chat_id):
            return SendResult(success=True, message_id=message_id or "g2")
        state = self._registry.stream_state(chat_id)
        delta = state.delta_for(content or "")
        if delta:
            await self._registry.send_frame(chat_id, P.assistant_delta(delta))
        return SendResult(success=True, message_id=message_id or "g2")

    def _session_key_for(self, source):
        # Mirror the flags the base handle_message uses, so our guard-wait key
        # always matches the gateway's session_key.
        extra = self.config.extra or {}
        return build_session_key(
            source,
            group_sessions_per_user=extra.get("group_sessions_per_user", True),
            thread_sessions_per_user=extra.get("thread_sessions_per_user", False),
        )

    def _source_for(self, chat_id: str):
        return self.build_source(chat_id=chat_id, chat_name="Even G2",
                                 chat_type="dm", user_id=chat_id, user_name="g2")

    def _session_title(self, session_id: str) -> str | None:
        db = getattr(self._session_store, "_db", None)
        get_session_title = getattr(db, "get_session_title", None)
        if callable(get_session_title):
            try:
                title = get_session_title(session_id)
            except Exception as e:
                log.debug("could not load session title for %s: %s", session_id, e)
                return None
            if isinstance(title, str) and title.strip():
                return title.strip()
        return None

    def _session_items(self) -> list[dict[str, Any]]:
        return session_items(self._session_store.list_sessions(), self._session_title)

    async def on_sessions_list(self, chat_id: str) -> None:
        items = self._session_items()
        active = self._session_by_chat.get(chat_id, "")
        await self._registry.send_frame(chat_id, P.sessions(items, active))

    async def on_sessions_switch(self, chat_id: str, target_id: str) -> None:
        source = self._source_for(chat_id)
        session_key = self._session_key_for(source)
        self._session_store.switch_session(session_key, target_id)
        self._session_by_chat[chat_id] = target_id
        await self._registry.send_frame(chat_id, P.active(target_id))
        items, ok = self._history_items(target_id)
        await self._registry.send_frame(chat_id, P.history(target_id, items, ok=ok))

    @staticmethod
    def _content_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            text = content.get("text") or content.get("content")
            return text if isinstance(text, str) else ""
        if isinstance(content, list):
            parts = []
            for part in content:
                text = EvenG2Adapter._content_text(part)
                if text:
                    parts.append(text)
            return "\n".join(parts)
        return ""

    def _history_items(self, session_id: str) -> tuple[list[dict[str, Any]], bool]:
        db = getattr(self._session_store, "_db", None)
        get_messages = getattr(db, "get_messages", None)
        if not callable(get_messages):
            return [], True

        try:
            messages = get_messages(session_id)
        except Exception as e:
            log.warning("could not load session history for %s: %s", session_id, e)
            return [], False

        items = []
        tool_labels: dict[str, str] = {}
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role == "assistant":
                self._remember_tool_labels(message, tool_labels)
            if role == "tool":
                tool = self._tool_history_item(message, tool_labels)
                if tool:
                    items.append(tool)
                continue
            if role in {"user", "assistant"}:
                text = self._content_text(message.get("content")).strip()
                if text:
                    items.append({"kind": role, "text": text})
        return self._cap_history_items(items), True

    @staticmethod
    def _remember_tool_labels(
        message: dict[str, Any],
        labels: dict[str, str],
    ) -> None:
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, str):
            try:
                tool_calls = json.loads(tool_calls)
            except Exception:
                return
        if not isinstance(tool_calls, list):
            return

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            call_id = call.get("id") or call.get("call_id") or call.get("tool_call_id")
            name, args = EvenG2Adapter._tool_call_name_args(call)
            if isinstance(call_id, str) and isinstance(name, str) and name.strip():
                labels[call_id] = tool_label(name.strip(), args)

    @staticmethod
    def _tool_call_name_args(call: dict[str, Any]) -> tuple[str | None, Any]:
        function = call.get("function")
        if not isinstance(function, dict):
            function = {}
        name = call.get("name") or call.get("tool_name") or function.get("name")
        args = (
            call.get("arguments")
            or call.get("args")
            or function.get("arguments")
            or function.get("args")
        )
        return name, args

    @staticmethod
    def _tool_history_item(
        message: dict[str, Any],
        labels: dict[str, str],
    ) -> dict[str, Any] | None:
        name = message.get("tool_name") or message.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        item = {
            "kind": "tool",
            "name": name.strip(),
            "running": False,
            "ok": EvenG2Adapter._tool_result_ok(message.get("content")),
        }
        call_id = message.get("tool_call_id") or message.get("call_id") or message.get("id")
        label = labels.get(call_id) if isinstance(call_id, str) else None
        if label and label != item["name"]:
            item["label"] = label
        return item

    @staticmethod
    def _tool_result_ok(content: Any) -> bool:
        text = EvenG2Adapter._content_text(content).strip()
        if not text:
            return True
        try:
            parsed = json.loads(text)
        except Exception:
            return True
        if not isinstance(parsed, dict):
            return True
        if parsed.get("exit_code") not in (None, 0):
            return False
        error = parsed.get("error")
        if error not in (None, "", False):
            return False
        return True

    @staticmethod
    def _cap_history_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        chars = 0
        for item in reversed(items):
            text = item.get("text")
            item_chars = len(text) if isinstance(text, str) else len(str(item.get("name", "")))
            if kept and (len(kept) >= HISTORY_MAX_ITEMS or chars + item_chars > HISTORY_MAX_CHARS):
                break
            kept.append(item)
            chars += item_chars
        return list(reversed(kept))

    def _is_command_output_suppressed(self, chat_id: str) -> bool:
        return self._suppressed_command_output.get(chat_id, 0) > 0

    async def _dispatch_command(
        self,
        chat_id: str,
        command: str,
        *,
        suppress_output: bool = False,
    ) -> None:
        source = self._source_for(chat_id)
        if suppress_output:
            self._suppressed_command_output[chat_id] = (
                self._suppressed_command_output.get(chat_id, 0) + 1
            )
        try:
            await self.handle_message(MessageEvent(
                text=command, message_type=MessageType.COMMAND, source=source))
        finally:
            if suppress_output:
                depth = self._suppressed_command_output.get(chat_id, 0) - 1
                if depth > 0:
                    self._suppressed_command_output[chat_id] = depth
                else:
                    self._suppressed_command_output.pop(chat_id, None)

    async def on_sessions_new(self, chat_id: str) -> None:
        source = self._source_for(chat_id)
        session_key = self._session_key_for(source)
        entry = self._session_store.reset_session(session_key, display_name="New session")
        if entry is None:
            entry = self._session_store.get_or_create_session(source, force_new=True)
        self._session_by_chat[chat_id] = entry.session_id
        await self._registry.send_frame(chat_id, P.active(entry.session_id))
        await self.on_sessions_list(chat_id)
        await self._registry.send_frame(chat_id, P.history(entry.session_id, []))

    async def on_stop(self, chat_id: str) -> None:
        await self._dispatch_command(chat_id, "/stop")

    def _ensure_home_channel(self, chat_id: str) -> None:
        """Set EVEN_G2_HOME_CHANNEL once so Hermes stops prompting to set a home
        channel on every fresh session. Mirrors what the gateway's /sethome does."""
        env_key = "EVEN_G2_HOME_CHANNEL"
        if os.environ.get(env_key):
            return
        os.environ[env_key] = chat_id
        try:
            # Import inside the function so tests can monkeypatch
            # hermes_cli.config.save_env_value without patching this module's namespace.
            from hermes_cli.config import save_env_value
            save_env_value(env_key, chat_id)
        except Exception as e:  # persistence is best-effort; process env still suppresses it
            log.warning("could not persist %s: %s", env_key, e)

    async def on_text(self, chat_id: str, text: str) -> None:
        self._ensure_home_channel(chat_id)
        source = self._source_for(chat_id)
        entry = self._session_store.get_or_create_session(source)
        self._session_by_chat[chat_id] = entry.session_id
        self._status.update(connected=self._registry.count(),
                            active_session=self._session_title(entry.session_id)
                            or entry.display_name or entry.session_id)
        session_key = self._session_key_for(source)
        self._registry.stream_state(chat_id).reset()
        await self.handle_message(MessageEvent(
            text=text, message_type=MessageType.TEXT, source=source))
        # Replace any stale poller for this device so a previous turn can't emit
        # a duplicate or premature turn.done.
        old = self._poller_tasks.pop(chat_id, None)
        if old is not None:
            old.cancel()
        self._poller_tasks[chat_id] = asyncio.create_task(
            self._emit_done_when_idle(session_key, chat_id))

    async def _emit_done_when_idle(self, session_key: str, chat_id: str) -> None:
        try:
            # Wait for the turn to register, then for the guard to clear.
            for _ in range(50):
                if session_key in self._active_sessions:
                    break
                await asyncio.sleep(self._idle_poll_seconds)
            while session_key in self._active_sessions:
                await asyncio.sleep(self._idle_poll_seconds)
            # Grace window: a chained/queued follow-up turn may re-register the
            # guard just after it clears; don't emit a premature turn.done.
            for _ in range(3):
                await asyncio.sleep(self._idle_poll_seconds)
                while session_key in self._active_sessions:
                    await asyncio.sleep(self._idle_poll_seconds)
            await self.on_sessions_list(chat_id)
            await self._registry.send_frame(chat_id, P.turn_done())
        finally:
            if self._poller_tasks.get(chat_id) is asyncio.current_task():
                self._poller_tasks.pop(chat_id, None)

    def _get_transcriber(self):
        want = resolve_active_name(self._bridge_cfg)
        if self._transcriber is None or want != self._active_name:
            if self._transcriber is not None:
                try:
                    self._transcriber.close()
                except Exception:
                    pass
            self._transcriber = load_active(self._bridge_cfg)
            self._active_name = want
            self._status.update(asr_active=self._active_name)
        return self._transcriber

    def refresh_status(self) -> None:
        self._status.update(connected=self._registry.count())

    async def on_audio(self, chat_id: str, pcm: bytes) -> None:
        self._status.update(mic="transcribing")
        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                None, self._get_transcriber().transcribe, pcm)
        finally:
            self._status.update(mic="idle")
        await self._registry.send_frame(chat_id, P.transcript(text))

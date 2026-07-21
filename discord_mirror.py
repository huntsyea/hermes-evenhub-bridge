"""Mirror G2 Q&A turns to Discord: one thread per question, answer inside.

Uses the gateway's existing bot token (DISCORD_BOT_TOKEN) so mirrored turns
match the thread-per-question shape of the Discord gateway. Configured via
EVENHUB_DISCORD_MIRROR_CHANNEL (text-channel id); unset = mirroring off.

Every call is fire-and-forget from the adapter: mirroring must never break
or delay a glasses turn, so all failures are logged and swallowed.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("hermes-evenhub-bridge")

_API = "https://discord.com/api/v10"
_CHUNK = 1900  # Discord message limit is 2000; leave headroom.
_THREAD_NAME_MAX = 80


def _channel() -> str:
    # Explicit mirror channel wins; otherwise reuse the Discord home channel.
    return (
        os.environ.get("EVENHUB_DISCORD_MIRROR_CHANNEL", "").strip()
        or os.environ.get("DISCORD_HOME_CHANNEL", "").strip()
    )


def enabled() -> bool:
    return bool(_channel() and os.environ.get("DISCORD_BOT_TOKEN", "").strip())


async def mirror_turn(question: str, answer: str) -> None:
    channel = _channel()
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not channel or not token:
        return
    try:
        import httpx

        headers = {"Authorization": f"Bot {token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{_API}/channels/{channel}/messages",
                headers=headers,
                json={"content": f"❓ {question}"[:2000]},
            )
            r.raise_for_status()
            msg_id = r.json()["id"]

            name = " ".join(question.split())[:_THREAD_NAME_MAX] or "Even G2"
            r = await client.post(
                f"{_API}/channels/{channel}/messages/{msg_id}/threads",
                headers=headers,
                json={"name": name, "auto_archive_duration": 1440},
            )
            r.raise_for_status()
            thread_id = r.json()["id"]

            text = answer.strip() or "(応答なし)"
            for i in range(0, len(text), _CHUNK):
                r = await client.post(
                    f"{_API}/channels/{thread_id}/messages",
                    headers=headers,
                    json={"content": text[i : i + _CHUNK]},
                )
                r.raise_for_status()
    except Exception as e:
        log.warning("discord mirror failed: %s", e)

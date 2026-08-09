"""Tests for the opt-in Discord Q&A mirror (no network)."""
import pytest

from hermes_evenhub_bridge import discord_mirror


class _FakeResponse:
    def __init__(self, payload, *, fail=False):
        self._payload = payload
        self._fail = fail

    def raise_for_status(self):
        if self._fail:
            raise RuntimeError("discord said no")

    def json(self):
        return self._payload


class _FakeClient:
    """Stands in for httpx.AsyncClient; records every POST."""

    def __init__(self, calls, fail_at=None, **_kwargs):
        self._calls = calls
        self._fail_at = fail_at

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, url, headers=None, json=None):
        index = len(self._calls)
        self._calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse({"id": f"id{index}"}, fail=index == self._fail_at)


@pytest.fixture
def calls(monkeypatch):
    """Patch httpx.AsyncClient and hand back the recorded POST list."""
    import httpx

    recorded = []
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: _FakeClient(recorded, **kw))
    return recorded


@pytest.fixture
def mirror_env(monkeypatch):
    monkeypatch.setenv("EVENHUB_DISCORD_MIRROR_CHANNEL", "555")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    monkeypatch.delenv("DISCORD_HOME_CHANNEL", raising=False)


# --- enabled() -----------------------------------------------------------

def test_enabled_requires_channel_and_token(monkeypatch):
    monkeypatch.delenv("EVENHUB_DISCORD_MIRROR_CHANNEL", raising=False)
    monkeypatch.delenv("DISCORD_HOME_CHANNEL", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    assert discord_mirror.enabled() is False

    monkeypatch.setenv("EVENHUB_DISCORD_MIRROR_CHANNEL", "1")
    assert discord_mirror.enabled() is False  # token still missing

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    assert discord_mirror.enabled() is True


def test_home_channel_is_the_fallback(monkeypatch):
    monkeypatch.delenv("EVENHUB_DISCORD_MIRROR_CHANNEL", raising=False)
    monkeypatch.setenv("DISCORD_HOME_CHANNEL", "home")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    assert discord_mirror.enabled() is True

    # An explicit mirror channel wins over the home channel.
    monkeypatch.setenv("EVENHUB_DISCORD_MIRROR_CHANNEL", "explicit")
    assert discord_mirror._channel() == "explicit"


# --- mirror_turn() -------------------------------------------------------

@pytest.mark.asyncio
async def test_mirror_posts_question_then_thread_then_answer(calls, mirror_env):
    await discord_mirror.mirror_turn("何時ですか", "3時です")

    assert len(calls) == 3
    q, thread, answer = calls
    assert q["url"].endswith("/channels/555/messages")
    assert q["json"]["content"] == "❓ 何時ですか"
    assert thread["url"].endswith("/channels/555/messages/id0/threads")
    assert thread["json"]["name"] == "何時ですか"
    # The answer goes into the thread created by the previous call.
    assert answer["url"].endswith("/channels/id1/messages")
    assert answer["json"]["content"] == "3時です"
    assert q["headers"]["Authorization"] == "Bot tok"


@pytest.mark.asyncio
async def test_thread_name_is_collapsed_and_capped(calls, mirror_env):
    await discord_mirror.mirror_turn("a\n\n  b   c" + "x" * 200, "ok")
    name = calls[1]["json"]["name"]
    assert "\n" not in name
    assert name.startswith("a b cxxx")
    assert len(name) == discord_mirror._THREAD_NAME_MAX


@pytest.mark.asyncio
async def test_long_answer_is_chunked(calls, mirror_env):
    await discord_mirror.mirror_turn("q", "y" * 4000)

    answer_posts = calls[2:]
    assert len(answer_posts) == 3  # 1900 + 1900 + 200
    assert [len(p["json"]["content"]) for p in answer_posts] == [1900, 1900, 200]
    assert all(len(p["json"]["content"]) <= 2000 for p in answer_posts)


@pytest.mark.asyncio
async def test_empty_answer_still_posts_a_placeholder(calls, mirror_env):
    await discord_mirror.mirror_turn("q", "   ")
    assert calls[2]["json"]["content"] == "(応答なし)"


@pytest.mark.asyncio
async def test_disabled_makes_no_requests(calls, monkeypatch):
    monkeypatch.delenv("EVENHUB_DISCORD_MIRROR_CHANNEL", raising=False)
    monkeypatch.delenv("DISCORD_HOME_CHANNEL", raising=False)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")

    await discord_mirror.mirror_turn("q", "a")
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", [0, 1, 2])
async def test_failures_are_swallowed_never_breaking_a_turn(
    monkeypatch, mirror_env, fail_at
):
    """A mirror failure must not propagate: the glasses turn already happened."""
    import httpx

    recorded = []
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kw: _FakeClient(recorded, fail_at=fail_at, **kw))

    await discord_mirror.mirror_turn("q", "a")  # must not raise

    # It stops at the failing call rather than pressing on.
    assert len(recorded) == fail_at + 1

from dataclasses import dataclass
from datetime import datetime

from hermes_evenhub_bridge.session_items import session_items


@dataclass
class Entry:
    session_id: str
    display_name: str | None
    updated_at: datetime | None
    input_tokens: int = 0
    output_tokens: int = 0


def test_session_items_prefers_generated_title_and_dedupes_by_session_id():
    older = datetime.fromtimestamp(10)
    newer = datetime.fromtimestamp(20)

    items = session_items(
        [
            Entry("s1", "New session", older),
            Entry("s1", "Even G2", newer),
            Entry("s2", "Two", older, input_tokens=2, output_tokens=3),
        ],
        lambda session_id: {"s1": "Generated topic"}.get(session_id),
    )

    assert items == [
        {"id": "s1", "title": "Generated topic", "updated": 20.0, "tokens": 0},
        {"id": "s2", "title": "Two", "updated": 10.0, "tokens": 5},
    ]


def test_session_items_falls_back_to_new_session_for_blank_titles():
    items = session_items([Entry("s1", "   ", None)], lambda _session_id: None)

    assert items == [{"id": "s1", "title": "New session", "updated": 0, "tokens": 0}]


def test_session_items_keeps_distinct_historical_new_sessions_from_db():
    items = session_items(
        [Entry("newest", "New session", datetime.fromtimestamp(30))],
        lambda _session_id: None,
        [
            {
                "id": "older",
                "title": None,
                "preview": "",
                "started_at": 10.0,
                "last_active": 10.0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
            {
                "id": "middle",
                "title": None,
                "preview": "",
                "started_at": 20.0,
                "last_active": 20.0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
            {
                "id": "titled",
                "title": "Generated title",
                "preview": "first user message",
                "started_at": 25.0,
                "last_active": 28.0,
                "input_tokens": 2,
                "output_tokens": 3,
            },
        ],
    )

    assert items == [
        {"id": "newest", "title": "New session", "updated": 30.0, "tokens": 0},
        {"id": "titled", "title": "Generated title", "updated": 28.0, "tokens": 5},
        {"id": "middle", "title": "New session", "updated": 20.0, "tokens": 0},
        {"id": "older", "title": "New session", "updated": 10.0, "tokens": 0},
    ]


def test_session_items_uses_rich_preview_when_title_missing():
    items = session_items(
        [],
        lambda _session_id: None,
        [{"id": "s1", "preview": "hello from glasses", "started_at": 1.0, "last_active": 2.0}],
    )

    assert items == [{"id": "s1", "title": "hello from glasses", "updated": 2.0, "tokens": 0}]

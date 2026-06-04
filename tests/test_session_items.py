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

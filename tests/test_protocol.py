import json
from hermes_evenhub_bridge import protocol as p


def test_parse_client_hello():
    msg = p.parse_client(json.dumps({"t": "hello", "token": "tok", "device": "g2"}))
    assert msg == {"t": "hello", "token": "tok", "device": "g2"}


def test_build_assistant():
    assert json.loads(p.assistant("hi")) == {"t": "assistant", "text": "hi"}


def test_reject_unknown_client():
    import pytest
    with pytest.raises(ValueError):
        p.parse_client(json.dumps({"t": "nope"}))


def test_tool_start_omits_empty_optional_fields():
    assert json.loads(p.tool_start("bash")) == {"t": "tool.start", "name": "bash"}
    assert json.loads(p.tool_start("bash", label="echo hi", emoji="⚙")) == {
        "t": "tool.start", "name": "bash", "label": "echo hi", "emoji": "⚙"}

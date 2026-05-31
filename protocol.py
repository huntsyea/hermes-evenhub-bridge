import json

CLIENT_TYPES = {
    "hello",
    "sessions.list",
    "sessions.switch",
    "sessions.new",
    "text",
    "stop",
    "audio.start",
    "audio.stop",
}


def parse_client(raw: str) -> dict:
    m = json.loads(raw)
    if not isinstance(m, dict) or m.get("t") not in CLIENT_TYPES:
        raise ValueError(f"bad client msg: {raw!r}")
    return m


def hello_ok(active, caps=None):
    return json.dumps({"t": "hello.ok", "caps": caps or {}, "active": active})


def sessions(items, active):
    return json.dumps({"t": "sessions", "items": items, "active": active})


def active(sid):
    return json.dumps({"t": "active", "id": sid})


def history(sid, items, ok=True):
    return json.dumps({"t": "history", "id": sid, "items": items, "ok": ok})


def transcript(text):
    return json.dumps({"t": "transcript", "text": text})


def assistant(text):
    return json.dumps({"t": "assistant", "text": text})


def assistant_delta(text: str) -> str:
    return json.dumps({"t": "assistant.delta", "text": text})


def tool_start(name, label="", emoji=""):
    msg = {"t": "tool.start", "name": name}
    if label: msg["label"] = label
    if emoji: msg["emoji"] = emoji
    return json.dumps(msg)


def tool_end(name, ok=True):
    return json.dumps({"t": "tool.end", "name": name, "ok": ok})


def turn_done():
    return json.dumps({"t": "turn.done"})


def error(msg):
    return json.dumps({"t": "error", "msg": msg})

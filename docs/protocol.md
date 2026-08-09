# Wire protocol

`server.py` ⇄ the glasses app speak one JSON frame protocol (plus raw binary PCM during an
audio stream). Every frame has a `t` (type) field.

> **The protocol is a contract.** `protocol.py` here and `protocol.ts` in the glasses app
> must stay in sync. Either side may change internals freely as long as these frames hold —
> when you change one, update the other in the same change.

## Client → bridge

| Frame | Payload | Meaning |
|---|---|---|
| `hello` | `token`, `device` | Authenticate + identify the device (this is the `chat_id`). |
| `text` | `text` | A typed/confirmed message → starts a turn. |
| `stop` | — | Interrupt the current turn (`/stop`). |
| `sessions.list` | — | Request the session list. |
| `sessions.switch` | `id` | Switch the active session. |
| `sessions.new` | — | Start a new session (`/new`). |
| `audio.start` / `audio.stop` | — | Bracket a PCM stream; raw binary frames in between are the audio. |
| `page.open` | `url` | Fetch a web page (`http`/`https` only) for the glasses page viewer. Pairing-gated like a turn. |

## Bridge → client

| Frame | Payload | Meaning |
|---|---|---|
| `hello.ok` | `active`, `caps` | Handshake accepted. |
| `assistant.delta` | `text` | Append-only chunk of the reply. |
| `tool.start` / `tool.end` | `name`, `ok` | A tool began / finished. |
| `turn.done` | — | The turn is complete (the gateway's per-turn guard cleared). |
| `sessions` | `items`, `active` | The session list. |
| `active` | `id` | The active session changed. |
| `history` | `id`, `items`, `ok` | Stored user/assistant stream items for a session; `ok=false` means history could not be loaded. |
| `transcript` | `text` | A voice transcription result. |
| `page.data` | `url`, `title`, `text`, `images`, `links` | A fetched page reduced for the display: main-content `text` (≤3000 chars), up to 3 `images` (`{data: base64 PNG ≤288×144 greyscale, width, height}`), and up to 19 in-page `links` (`{url, label}`). |
| `page.error` | `url`, `msg` | The fetch for `url` failed (bad scheme, blocked host, network error, or unpaired device). |
| `error` | `msg` | A recoverable error; the connection stays open. |

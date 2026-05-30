# Third-Party Notices

`hermes-evenhub-bridge` is MIT-licensed (see `LICENSE`). It uses and/or redistributes the
following third-party components under their own licenses.

## Bundled / redistributed

- **FluidAudio** — Apache License 2.0 — https://github.com/FluidInference/FluidAudio
  The prebuilt macOS ASR sidecar binary published to this project's GitHub Releases is a
  Swift executable that links FluidAudio. Redistribution is under Apache-2.0; a copy of the
  Apache-2.0 license and attribution are retained per its terms.

## Runtime dependencies (installed via pip, not redistributed here)

- **faster-whisper** — MIT — https://github.com/SYSTRAN/faster-whisper
- **websockets** — BSD-3-Clause — https://github.com/python-websockets/websockets
- **numpy** — BSD-3-Clause — https://github.com/numpy/numpy

## Models (downloaded at runtime, not redistributed here)

- **Parakeet-TDT 0.6B (v2/v3)** — CC-BY-4.0 — NVIDIA —
  https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
  Downloaded on first use by the ASR sidecar. Attribution to NVIDIA per CC-BY-4.0.
- **Whisper (tiny)** weights via faster-whisper / CTranslate2 — MIT (model weights per their
  respective model cards) — fetched on first use to `~/.cache/huggingface`.

## Runtime host (not bundled)

- **Hermes gateway** — imported in-process at runtime; this plugin does not bundle or
  redistribute it.

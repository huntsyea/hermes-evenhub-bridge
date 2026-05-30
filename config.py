import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BridgeConfig:
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    token: str = ""
    asr_sidecar_bin: str = "sidecar/.build/release/g2-asr-sidecar"
    asr_state_path: str = ""

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            ws_host=os.environ.get("EVENHUB_BRIDGE_HOST", "0.0.0.0"),
            ws_port=int(os.environ.get("EVENHUB_BRIDGE_PORT", "8765")),
            token=os.environ.get("EVENHUB_BRIDGE_TOKEN", ""),
            asr_sidecar_bin=os.environ.get(
                "EVENHUB_ASR_SIDECAR_BIN", "sidecar/.build/release/g2-asr-sidecar"),
            asr_state_path=os.environ.get(
                "EVENHUB_ASR_STATE",
                str(Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
                    / "even_g2_asr.json")),
        )

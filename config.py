import os
from dataclasses import dataclass


@dataclass
class BridgeConfig:
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    token: str = ""
    asr_model: str = "base"

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            ws_host=os.environ.get("EVENHUB_BRIDGE_HOST", "0.0.0.0"),
            ws_port=int(os.environ.get("EVENHUB_BRIDGE_PORT", "8765")),
            token=os.environ.get("EVENHUB_BRIDGE_TOKEN", ""),
            asr_model=os.environ.get("EVENHUB_ASR_MODEL", "base"),
        )

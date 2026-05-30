import argparse
import asyncio

from .config import BridgeConfig
from . import asr as asr_pkg
from .asr import REGISTRY
from .asr.state import set_active, get_active


async def _run_server():
    from gateway.config import PlatformConfig  # gateway only needed to run the server
    from .adapter import EvenG2Adapter
    adapter = EvenG2Adapter(PlatformConfig(extra={}))
    await adapter.connect()
    print(f"[evenhub-bridge] listening on port {adapter.bound_port}")
    await asyncio.Future()


def _cmd_asr(args) -> int:
    cfg = BridgeConfig.from_env()
    if args.asr_cmd == "list":
        active = get_active(cfg.asr_state_path) or asr_pkg.DEFAULT_ACTIVE
        for name, spec in REGISTRY.items():
            try:
                backend = asr_pkg._build_backend(name, cfg)
                installed = "yes" if backend.is_installed() else "no"
            except Exception:
                installed = "no"
            mark = "*" if name == active else " "
            print(f"{mark} {name:<22} {spec.backend:<10} installed={installed}")
        return 0
    if args.asr_cmd == "set":
        if args.name not in REGISTRY:
            print(f"unknown model: {args.name}")
            return 2
        set_active(args.name, cfg.asr_state_path)
        print(f"active model set to {args.name}")
        return 0
    if args.asr_cmd == "download":
        if args.name not in REGISTRY:
            print(f"unknown model: {args.name}")
            return 2
        asr_pkg._build_backend(args.name, cfg).ensure_downloaded()
        print(f"downloaded {args.name}")
        return 0
    return 2


def _cmd_url() -> int:
    from . import net
    cfg = BridgeConfig.from_env()
    ts = net.detect_tailscale()
    print(net.preferred_connect_url(cfg, ts))
    if ts and (ts.get("magic_dns") or ts.get("ip")):
        print(f"  tailscale: {ts.get('magic_dns') or ts.get('ip')} "
              f"(online={ts.get('online')})")
    print(f"  net_mode: {cfg.net_mode}  (set EVENHUB_BRIDGE_NET=both|tailnet|lan)")
    print("  Use this URL for VITE_BRIDGE_LAN_URL in the glasses app's .env.local,")
    print("  and add it to app.json's network whitelist (exact match).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-evenhub-bridge")
    sub = parser.add_subparsers(dest="cmd")

    asr_p = sub.add_parser("asr", help="Manage ASR models")
    asr_sub = asr_p.add_subparsers(dest="asr_cmd")
    asr_sub.add_parser("list", help="List available ASR models")
    d = asr_sub.add_parser("download", help="Download an ASR model")
    d.add_argument("name", help="Model name from registry")
    s = asr_sub.add_parser("set", help="Set the active ASR model")
    s.add_argument("name", help="Model name from registry")

    sub.add_parser("url", help="Print the ws:// URL the glasses should connect to")

    args = parser.parse_args(argv)

    if args.cmd == "asr":
        return _cmd_asr(args)
    if args.cmd == "url":
        return _cmd_url()

    # Default: run the bridge server (existing behavior)
    asyncio.run(_run_server())
    return 0


if __name__ == "__main__":
    main()

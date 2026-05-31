"""User-facing CLI, exposed through Hermes as ``hermes even-g2 ...`` via
``ctx.register_cli_command``. Kept import-light (heavy deps imported lazily in the
handlers) so registering the command never pulls in numpy/asr."""
from __future__ import annotations


def setup_parser(parser) -> None:
    """Build the ``hermes even-g2 <...>`` argparse tree on *parser*."""
    sub = parser.add_subparsers(dest="eg2_cmd")
    sub.add_parser("url", help="Print the URL the Even app should connect to")
    setup = sub.add_parser("setup", help="Configure local bridge and Tailscale Serve")
    setup.add_argument("--serve-port", type=int, default=None,
                       help="Tailscale Serve HTTPS port, default 8443")
    setup.add_argument("--skip-serve", action="store_true",
                       help="Persist local bridge settings only")
    setup.add_argument("--force-token", action="store_true",
                       help="Replace any existing bridge token and print the new token once")
    asr_p = sub.add_parser("asr", help="Manage ASR models")
    asr_sub = asr_p.add_subparsers(dest="asr_cmd")
    asr_sub.add_parser("list", help="List available ASR models")
    d = asr_sub.add_parser("download", help="Download an ASR model")
    d.add_argument("name", help="Model name from the registry")
    s = asr_sub.add_parser("set", help="Set the active ASR model")
    s.add_argument("name", help="Model name from the registry")


def run(args) -> int:
    """Dispatch a parsed ``hermes even-g2`` invocation."""
    cmd = getattr(args, "eg2_cmd", None)
    if cmd == "url":
        return _cmd_url()
    if cmd == "setup":
        return _cmd_setup(args)
    if cmd == "asr":
        return _cmd_asr(args)
    print("usage: hermes even-g2 <url | setup | asr list|download <name>|set <name>>")
    return 2


def _cmd_url() -> int:
    from .config import BridgeConfig
    from . import net
    cfg = BridgeConfig.from_env()
    _bind, url, ts = net.resolve(cfg)
    public_url = net.public_connect_url(cfg, ts)
    print(public_url or url)
    if public_url:
        print("  transport: private WSS via Tailscale Serve")
        print(f"  local bridge: {url}")
    else:
        print("  transport: local ws:// fallback")
    if ts and (ts.get("magic_dns") or ts.get("ip")):
        print(f"  tailscale: {ts.get('magic_dns') or ts.get('ip')} "
              f"(online={ts.get('online')})")
    print(f"  net_mode: {cfg.net_mode}  (set EVENHUB_BRIDGE_NET=both|tailnet|lan)")
    if not public_url:
        print("  Run `hermes even-g2 setup` to configure the recommended WSS app URL.")
    return 0


def _cmd_setup(args) -> int:
    from . import setup_flow
    try:
        local = setup_flow.configure_local_bridge(
            force_token=getattr(args, "force_token", False),
        )
        print("Local bridge configuration written.")
        if local["token_generated"]:
            print("Pairing token:")
            print(local["token"])
        if local["restart_required"]:
            print("Restart Hermes Gateway before relying on changed host/token settings.")
        if getattr(args, "skip_serve", False):
            return 0
        served = setup_flow.enable_tailscale_serve(serve_port=getattr(args, "serve_port", None))
    except setup_flow.SetupError as exc:
        print(f"setup failed: {exc}")
        return 1
    print("Tailscale Serve configured.")
    print(f"App URL: {served['public_url']}")
    print("Enter the App URL and pairing token in the Even companion app.")
    return 0


def _cmd_asr(args) -> int:
    from .config import BridgeConfig
    from . import asr as asr_pkg
    from .asr import REGISTRY
    from .asr.state import set_active, get_active
    cfg = BridgeConfig.from_env()
    cmd = getattr(args, "asr_cmd", None)
    if cmd == "list":
        active = get_active(cfg.asr_state_path) or asr_pkg.DEFAULT_ACTIVE
        for name, spec in REGISTRY.items():
            try:
                installed = "yes" if asr_pkg._build_backend(name, cfg).is_installed() else "no"
            except Exception:
                installed = "no"
            mark = "*" if name == active else " "
            print(f"{mark} {name:<22} {spec.backend:<10} installed={installed}")
        return 0
    if cmd == "set":
        if args.name not in REGISTRY:
            print(f"unknown model: {args.name}")
            return 2
        set_active(args.name, cfg.asr_state_path)
        print(f"active model set to {args.name}")
        return 0
    if cmd == "download":
        if args.name not in REGISTRY:
            print(f"unknown model: {args.name}")
            return 2
        asr_pkg._build_backend(args.name, cfg).ensure_downloaded()
        print(f"downloaded {args.name}")
        return 0
    print("usage: hermes even-g2 asr <list | download <name> | set <name>>")
    return 2

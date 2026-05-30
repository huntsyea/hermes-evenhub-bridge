"""Direct entry point mirroring the `hermes even-g2 ...` CLI (registered via
ctx.register_cli_command). Mainly for tests/dev; end users run `hermes even-g2`."""
import argparse

from . import cli


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-evenhub-bridge")
    cli.setup_parser(parser)
    args = parser.parse_args(argv)
    return cli.run(args)


if __name__ == "__main__":
    raise SystemExit(main())

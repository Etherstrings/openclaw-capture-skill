"""CLI entrypoint for dispatching payloads through the wrapper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import Settings
from .dispatcher import CaptureDispatcher
from .server import run_server


def _load_payload(args: argparse.Namespace) -> dict:
    if args.payload_json:
        return json.loads(args.payload_json)
    if args.payload_file == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw capture wrapper runtime")
    subparsers = parser.add_subparsers(dest="command")

    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch one payload")
    dispatch_parser.add_argument("--payload-file", default="-", help="JSON payload path or - for stdin")
    dispatch_parser.add_argument("--payload-json", help="Inline JSON payload")

    serve_parser = subparsers.add_parser("serve", help="Run wrapper HTTP listener")
    serve_parser.add_argument("--host", help="Bind host")
    serve_parser.add_argument("--port", type=int, help="Bind port")

    args = parser.parse_args()
    settings = Settings.from_env()

    if args.command == "serve":
        if args.host:
            settings.listen_host = args.host
        if args.port:
            settings.listen_port = args.port
        return run_server(settings)

    if args.command is None:
        args = argparse.Namespace(command="dispatch", payload_file="-", payload_json=None)

    payload = _load_payload(args)
    dispatcher = CaptureDispatcher(settings)
    job = dispatcher.dispatch(payload)
    print(json.dumps(job, ensure_ascii=False, indent=2))
    return 1 if str(job.get("status")) == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

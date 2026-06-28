"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio

from .ble_probe import probe, scan


def main() -> None:
    parser = argparse.ArgumentParser(prog="dafit-open")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan for nearby BLE devices")
    scan_parser.add_argument("--timeout", type=float, default=10.0)
    scan_parser.add_argument("--verbose", action="store_true")

    probe_parser = subparsers.add_parser("probe", help="connect and probe a watch")
    probe_parser.add_argument("address")
    probe_parser.add_argument("--timeout", type=float, default=45.0)
    probe_parser.add_argument("--scan-timeout", type=float, default=10.0)
    probe_parser.add_argument("--retries", type=int, default=3)
    probe_parser.add_argument("--pair", action="store_true")
    probe_parser.add_argument("--direct", action="store_true")

    args = parser.parse_args()
    if args.command == "scan":
        asyncio.run(scan(args.timeout, args.verbose))
    elif args.command == "probe":
        asyncio.run(
            probe(
                args.address,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
            )
        )

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

    probe_parser = subparsers.add_parser("probe", help="connect and probe a watch")
    probe_parser.add_argument("address")
    probe_parser.add_argument("--timeout", type=float, default=20.0)

    args = parser.parse_args()
    if args.command == "scan":
        asyncio.run(scan(args.timeout))
    elif args.command == "probe":
        asyncio.run(probe(args.address, args.timeout))

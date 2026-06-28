"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio

from .ble_probe import device_info, probe, scan, set_watch_face


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
    probe_parser.add_argument("--json-out", help="write a structured JSON capture")
    probe_parser.add_argument(
        "--query-set",
        choices=["default", "watchface", "watchface-support"],
        default="default",
    )

    info_parser = subparsers.add_parser("device-info", help="read GATT characteristics")
    info_parser.add_argument("address")
    info_parser.add_argument("--timeout", type=float, default=45.0)
    info_parser.add_argument("--scan-timeout", type=float, default=10.0)
    info_parser.add_argument("--retries", type=int, default=3)
    info_parser.add_argument("--pair", action="store_true")
    info_parser.add_argument("--direct", action="store_true")
    info_parser.add_argument("--json-out", help="write a structured JSON capture")

    set_face_parser = subparsers.add_parser(
        "set-watch-face",
        help="set the active watch-face slot",
    )
    set_face_parser.add_argument("address")
    set_face_parser.add_argument("index", type=int, help="slot index from watch-face list")
    set_face_parser.add_argument("--timeout", type=float, default=45.0)
    set_face_parser.add_argument("--scan-timeout", type=float, default=10.0)
    set_face_parser.add_argument("--retries", type=int, default=3)
    set_face_parser.add_argument("--pair", action="store_true")
    set_face_parser.add_argument("--direct", action="store_true")
    set_face_parser.add_argument("--json-out", help="write a structured JSON capture")
    set_face_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this changes watch state",
    )

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
                query_set=args.query_set,
                json_out=args.json_out,
            )
        )
    elif args.command == "set-watch-face":
        if not args.confirm:
            parser.error("set-watch-face changes watch state; rerun with --confirm")
        asyncio.run(
            set_watch_face(
                args.address,
                args.index,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )
    elif args.command == "device-info":
        asyncio.run(
            device_info(
                args.address,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )


if __name__ == "__main__":
    main()

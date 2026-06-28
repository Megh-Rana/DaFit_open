"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio

from .ble_probe import (
    device_info,
    probe,
    scan,
    set_watch_face,
    sync_training,
    training_detail,
    training_series,
    watch_faces,
)
from .capture_export import load_workout_summaries, write_workout_export
from .state_export import load_app_state, write_app_state
from .tui import run_capture_tui
from .watchface_export import load_watch_face_state, write_watch_face_export


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
        choices=[
            "default",
            "health-basic",
            "health-extended",
            "health-history",
            "watchface",
            "watchface-support",
        ],
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

    watch_faces_parser = subparsers.add_parser(
        "watch-faces",
        help="query installed/current watch-face state",
    )
    watch_faces_parser.add_argument("address")
    watch_faces_parser.add_argument("--timeout", type=float, default=45.0)
    watch_faces_parser.add_argument("--scan-timeout", type=float, default=10.0)
    watch_faces_parser.add_argument("--retries", type=int, default=3)
    watch_faces_parser.add_argument("--pair", action="store_true")
    watch_faces_parser.add_argument("--direct", action="store_true")
    watch_faces_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=3.0,
        help="seconds to wait for each watch-face response",
    )
    watch_faces_parser.add_argument(
        "--extended",
        action="store_true",
        help="also send extra read-only watch-face support probes",
    )
    watch_faces_parser.add_argument("--json-out", help="write a structured JSON capture")

    training_detail_parser = subparsers.add_parser(
        "training-detail",
        help="query stored training detail by history id",
    )
    training_detail_parser.add_argument("address")
    training_detail_parser.add_argument("ids", nargs="+", type=int, help="training history ids")
    training_detail_parser.add_argument("--timeout", type=float, default=45.0)
    training_detail_parser.add_argument("--scan-timeout", type=float, default=10.0)
    training_detail_parser.add_argument("--retries", type=int, default=3)
    training_detail_parser.add_argument("--pair", action="store_true")
    training_detail_parser.add_argument("--direct", action="store_true")
    training_detail_parser.add_argument("--json-out", help="write a structured JSON capture")

    training_series_parser = subparsers.add_parser(
        "training-series",
        help="query stored training heart-rate, step, or distance chunks",
    )
    training_series_parser.add_argument("address")
    training_series_parser.add_argument("id", type=int, help="training history id")
    training_series_parser.add_argument(
        "--kind",
        choices=["all", "heart-rate", "steps", "distance"],
        action="append",
        default=None,
        help="series kind to query; can be repeated",
    )
    training_series_parser.add_argument("--offset", type=int, default=0)
    training_series_parser.add_argument(
        "--chunk-timeout",
        type=float,
        default=6.0,
        help="seconds to wait for each training series chunk",
    )
    training_series_parser.add_argument("--timeout", type=float, default=45.0)
    training_series_parser.add_argument("--scan-timeout", type=float, default=10.0)
    training_series_parser.add_argument("--retries", type=int, default=3)
    training_series_parser.add_argument("--pair", action="store_true")
    training_series_parser.add_argument("--direct", action="store_true")
    training_series_parser.add_argument("--json-out", help="write a structured JSON capture")

    sync_training_parser = subparsers.add_parser(
        "sync-training",
        help="discover stored trainings and fetch details/series in one session",
    )
    sync_training_parser.add_argument("address")
    sync_training_parser.add_argument(
        "--kind",
        choices=["all", "heart-rate", "steps", "distance"],
        action="append",
        default=None,
        help="series kind to query for each workout; can be repeated",
    )
    sync_training_parser.add_argument(
        "--chunk-timeout",
        type=float,
        default=6.0,
        help="seconds to wait for each training response",
    )
    sync_training_parser.add_argument("--timeout", type=float, default=45.0)
    sync_training_parser.add_argument("--scan-timeout", type=float, default=10.0)
    sync_training_parser.add_argument("--retries", type=int, default=3)
    sync_training_parser.add_argument("--pair", action="store_true")
    sync_training_parser.add_argument("--direct", action="store_true")
    sync_training_parser.add_argument("--json-out", help="write a structured JSON capture")

    export_parser = subparsers.add_parser(
        "export-captures",
        help="export structured summaries from JSON captures",
    )
    export_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--output", help="write export to a file instead of stdout")
    export_parser.add_argument(
        "--no-samples",
        action="store_true",
        help="omit sample arrays from JSON output",
    )

    export_faces_parser = subparsers.add_parser(
        "export-watch-faces",
        help="export watch-face state from JSON captures",
    )
    export_faces_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_faces_parser.add_argument("--output", help="write export to a file instead of stdout")

    export_state_parser = subparsers.add_parser(
        "export-state",
        help="export an app-ready device/watch-face/workout state document",
    )
    export_state_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_state_parser.add_argument("--output", help="write export to a file instead of stdout")
    export_state_parser.add_argument(
        "--include-samples",
        action="store_true",
        help="include workout sample arrays in the exported state",
    )

    tui_parser = subparsers.add_parser(
        "tui",
        help="browse captured workout summaries in a terminal UI",
    )
    tui_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
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
    elif args.command == "watch-faces":
        asyncio.run(
            watch_faces(
                args.address,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                wait_timeout=args.wait_timeout,
                extended=args.extended,
                json_out=args.json_out,
            )
        )
    elif args.command == "training-detail":
        asyncio.run(
            training_detail(
                args.address,
                args.ids,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )
    elif args.command == "training-series":
        asyncio.run(
            training_series(
                args.address,
                args.id,
                args.kind or ["all"],
                args.offset,
                args.chunk_timeout,
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )
    elif args.command == "sync-training":
        asyncio.run(
            sync_training(
                args.address,
                args.kind or ["heart-rate"],
                args.timeout,
                args.scan_timeout,
                args.retries,
                pair=args.pair,
                direct=args.direct,
                chunk_timeout=args.chunk_timeout,
                json_out=args.json_out,
            )
        )
    elif args.command == "export-captures":
        workouts = load_workout_summaries(args.paths)
        write_workout_export(
            workouts,
            args.format,
            output=args.output,
            include_samples=not args.no_samples,
        )
    elif args.command == "export-watch-faces":
        state = load_watch_face_state(args.paths)
        write_watch_face_export(state, output=args.output)
    elif args.command == "export-state":
        state = load_app_state(args.paths, include_samples=args.include_samples)
        write_app_state(state, output=args.output)
    elif args.command == "tui":
        run_capture_tui(args.paths)


if __name__ == "__main__":
    main()

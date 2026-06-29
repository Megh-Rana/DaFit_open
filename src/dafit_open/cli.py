"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio

from .alarm_export import load_alarm_state, write_alarm_export
from .ble_probe import (
    device_info,
    probe,
    scan,
    set_settings,
    set_watch_face,
    sync_training,
    training_detail,
    training_series,
    watch_faces,
    write_alarm_packets,
)
from .collector import collect
from .capture_export import load_workout_summaries, write_workout_export
from .settings_export import load_settings_state, write_settings_export
from .state_export import load_app_state, write_app_state
from .tui import run_capture_tui
from .watchface_export import load_watch_face_state, write_watch_face_export
from .protocol import (
    AlarmInfo,
    Packet,
    delete_all_new_alarms_packet,
    delete_new_alarm_packet,
    hex_bytes,
    set_legacy_alarm_packet,
    set_new_alarm_packet,
)


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
            "alarms",
            "daily-settings",
            "default",
            "health-basic",
            "health-extended",
            "health-history",
            "settings-basic",
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

    set_settings_parser = subparsers.add_parser(
        "set-settings",
        help="set basic watch settings",
    )
    set_settings_parser.add_argument("address")
    set_settings_parser.add_argument("--goal-steps", type=int)
    set_settings_parser.add_argument("--time-system", type=int, choices=[0, 1])
    set_settings_parser.add_argument(
        "--display-time",
        choices=["on", "off"],
        help="enable or disable display-time setting",
    )
    set_settings_parser.add_argument(
        "--dnd",
        nargs=2,
        metavar=("START", "END"),
        help="set do-not-disturb period as HH:MM HH:MM",
    )
    set_settings_parser.add_argument("--timeout", type=float, default=45.0)
    set_settings_parser.add_argument("--scan-timeout", type=float, default=10.0)
    set_settings_parser.add_argument("--retries", type=int, default=3)
    set_settings_parser.add_argument("--pair", action="store_true")
    set_settings_parser.add_argument("--direct", action="store_true")
    set_settings_parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip settings-basic verification query after writing",
    )
    set_settings_parser.add_argument("--json-out", help="write a structured JSON capture")
    set_settings_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this changes watch state",
    )

    set_alarm_parser = subparsers.add_parser(
        "set-alarm",
        help="create or update an alarm",
    )
    set_alarm_parser.add_argument("address")
    set_alarm_parser.add_argument("--id", type=int, required=True, help="alarm id/slot")
    set_alarm_parser.add_argument("--time", required=True, help="alarm time as HH:MM")
    set_alarm_parser.add_argument(
        "--enabled",
        choices=["on", "off"],
        default="on",
        help="whether the alarm is enabled",
    )
    set_alarm_parser.add_argument(
        "--repeat-mask",
        type=_parse_byte,
        default=0,
        help="repeat mask byte for non-date alarms; 127 means every day",
    )
    set_alarm_parser.add_argument(
        "--date",
        help="one-shot date as YYYY-MM-DD; valid watch encoding range is 2015-2030",
    )
    set_alarm_parser.add_argument(
        "--everyday",
        action="store_true",
        help="shortcut for repeat-mask 127",
    )
    set_alarm_parser.add_argument(
        "--legacy",
        action="store_true",
        help="use legacy 0x11 setter instead of new 0xB9 setter",
    )
    set_alarm_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print packet bytes without connecting",
    )
    set_alarm_parser.add_argument("--timeout", type=float, default=45.0)
    set_alarm_parser.add_argument("--scan-timeout", type=float, default=10.0)
    set_alarm_parser.add_argument("--retries", type=int, default=3)
    set_alarm_parser.add_argument("--pair", action="store_true")
    set_alarm_parser.add_argument("--direct", action="store_true")
    set_alarm_parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip alarms verification query after writing",
    )
    set_alarm_parser.add_argument("--json-out", help="write a structured JSON capture")
    set_alarm_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this changes watch state",
    )

    delete_alarm_parser = subparsers.add_parser(
        "delete-alarm",
        help="delete one or all new-format alarms",
    )
    delete_alarm_parser.add_argument("address")
    delete_alarm_group = delete_alarm_parser.add_mutually_exclusive_group(required=True)
    delete_alarm_group.add_argument("--id", type=int, help="new alarm id to delete")
    delete_alarm_group.add_argument(
        "--all",
        action="store_true",
        help="delete all new-format alarms",
    )
    delete_alarm_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print packet bytes without connecting",
    )
    delete_alarm_parser.add_argument("--timeout", type=float, default=45.0)
    delete_alarm_parser.add_argument("--scan-timeout", type=float, default=10.0)
    delete_alarm_parser.add_argument("--retries", type=int, default=3)
    delete_alarm_parser.add_argument("--pair", action="store_true")
    delete_alarm_parser.add_argument("--direct", action="store_true")
    delete_alarm_parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip alarms verification query after writing",
    )
    delete_alarm_parser.add_argument("--json-out", help="write a structured JSON capture")
    delete_alarm_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this changes watch state",
    )

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

    collect_parser = subparsers.add_parser(
        "collect",
        help="refresh known device/watch-face/training data and export app state",
    )
    collect_parser.add_argument("address")
    collect_parser.add_argument("--out-dir", help="capture output directory")
    collect_parser.add_argument("--timeout", type=float, default=45.0)
    collect_parser.add_argument("--scan-timeout", type=float, default=10.0)
    collect_parser.add_argument("--retries", type=int, default=1)
    collect_parser.add_argument("--pair", action="store_true")
    collect_parser.add_argument("--direct", action="store_true")
    collect_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=4.0,
        help="seconds to wait for each watch-face response",
    )
    collect_parser.add_argument(
        "--training-kind",
        choices=["all", "heart-rate", "steps", "distance"],
        action="append",
        default=None,
        help="training series kind to sync; can be repeated",
    )
    collect_parser.add_argument(
        "--chunk-timeout",
        type=float,
        default=8.0,
        help="seconds to wait for each training response",
    )
    collect_parser.add_argument(
        "--no-training",
        action="store_true",
        help="skip training sync for a faster collection",
    )
    collect_parser.add_argument("--export-state", help="app-state JSON output path")
    collect_parser.add_argument(
        "--include-samples",
        action="store_true",
        help="include workout sample arrays in the exported state",
    )

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

    export_settings_parser = subparsers.add_parser(
        "export-settings",
        help="export settings state from JSON captures",
    )
    export_settings_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_settings_parser.add_argument("--output", help="write export to a file instead of stdout")

    export_alarms_parser = subparsers.add_parser(
        "export-alarms",
        help="export alarm state from JSON captures",
    )
    export_alarms_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_alarms_parser.add_argument("--output", help="write export to a file instead of stdout")

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
    elif args.command == "set-settings":
        if not args.confirm:
            parser.error("set-settings changes watch state; rerun with --confirm")
        if (
            args.goal_steps is None
            and args.time_system is None
            and args.display_time is None
            and args.dnd is None
        ):
            parser.error("set-settings requires at least one setting option")
        dnd = None
        if args.dnd is not None:
            try:
                start_hour, start_minute = _parse_hhmm(args.dnd[0])
                end_hour, end_minute = _parse_hhmm(args.dnd[1])
            except argparse.ArgumentTypeError as exc:
                parser.error(str(exc))
            dnd = (start_hour, start_minute, end_hour, end_minute)
        asyncio.run(
            set_settings(
                args.address,
                goal_steps=args.goal_steps,
                time_system=args.time_system,
                display_time=None if args.display_time is None else args.display_time == "on",
                dnd=dnd,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                verify=not args.no_verify,
                json_out=args.json_out,
            )
        )
    elif args.command == "set-alarm":
        if args.date and args.everyday:
            parser.error("set-alarm accepts either --date or --everyday, not both")
        if args.everyday:
            repeat_mask = 127
        else:
            repeat_mask = args.repeat_mask
        try:
            hour, minute = _parse_hhmm(args.time)
            alarm = AlarmInfo(
                id=args.id,
                enabled=args.enabled == "on",
                hour=hour,
                minute=minute,
                repeat_mode=repeat_mask,
                date=args.date,
            )
            packet = set_legacy_alarm_packet(alarm) if args.legacy else set_new_alarm_packet(alarm)
        except (argparse.ArgumentTypeError, ValueError) as exc:
            parser.error(str(exc))
        packets = [("set legacy alarm" if args.legacy else "set new alarm", packet)]
        if args.dry_run:
            _print_packets(packets)
            return
        if not args.confirm:
            parser.error("set-alarm changes watch state; rerun with --confirm or --dry-run")
        asyncio.run(
            write_alarm_packets(
                args.address,
                "set-legacy" if args.legacy else "set-new",
                packets,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                verify=not args.no_verify,
                json_out=args.json_out,
            )
        )
    elif args.command == "delete-alarm":
        try:
            if args.all:
                packets = [("delete all new alarms", delete_all_new_alarms_packet())]
                operation = "delete-all-new"
            else:
                packets = [(f"delete new alarm id={args.id}", delete_new_alarm_packet(args.id))]
                operation = "delete-new"
        except ValueError as exc:
            parser.error(str(exc))
        if args.dry_run:
            _print_packets(packets)
            return
        if not args.confirm:
            parser.error("delete-alarm changes watch state; rerun with --confirm or --dry-run")
        asyncio.run(
            write_alarm_packets(
                args.address,
                operation,
                packets,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                verify=not args.no_verify,
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
    elif args.command == "collect":
        asyncio.run(
            collect(
                args.address,
                out_dir=args.out_dir,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                wait_timeout=args.wait_timeout,
                include_training=not args.no_training,
                training_kinds=args.training_kind,
                chunk_timeout=args.chunk_timeout,
                export_state=args.export_state,
                include_samples=args.include_samples,
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
    elif args.command == "export-settings":
        state = load_settings_state(args.paths)
        write_settings_export(state, output=args.output)
    elif args.command == "export-alarms":
        state = load_alarm_state(args.paths)
        write_alarm_export(state, output=args.output)
    elif args.command == "export-state":
        state = load_app_state(args.paths, include_samples=args.include_samples)
        write_app_state(state, output=args.output)
    elif args.command == "tui":
        run_capture_tui(args.paths)


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected HH:MM, got {value!r}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise argparse.ArgumentTypeError(f"expected HH:MM within 00:00-23:59, got {value!r}")
    return hour, minute


def _parse_byte(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected byte value, got {value!r}") from exc
    if not 0 <= parsed <= 0xFF:
        raise argparse.ArgumentTypeError(f"expected byte value within 0-255, got {value!r}")
    return parsed


def _print_packets(packets: list[tuple[str, Packet]]) -> None:
    for label, packet in packets:
        data = packet.build()
        print(f"{label}: cmd=0x{packet.command:02X} payload={hex_bytes(packet.payload)}")
        print(f"  frame: {hex_bytes(data)}")


if __name__ == "__main__":
    main()

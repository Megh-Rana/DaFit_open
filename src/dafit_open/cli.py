"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json

from .alarm_export import load_alarm_state, write_alarm_export
from .app_log_import import import_app_logs, write_imported_app_log
from .ble_probe import (
    device_info,
    probe,
    scan,
    set_settings,
    set_watch_face,
    sync_training,
    training_detail,
    training_series,
    upload_original_background,
    upload_store_watch_face,
    upload_watch_face_raw,
    watch_faces,
    write_alarm_packets,
)
from .collector import collect
from .capture_export import load_workout_summaries, write_workout_export
from .settings_export import load_settings_state, write_settings_export
from .packet_export import (
    load_packet_events,
    summarize_packet_events,
    write_packet_events,
    write_packet_summary,
)
from .state_export import (
    load_app_state,
    summarize_app_state,
    write_app_state,
    write_app_state_summary,
)
from .tui import run_capture_tui
from .watchface_export import load_watch_face_state, write_watch_face_export
from .watchface_image import (
    build_original_background_package,
    build_watch_face_package,
    inspect_watch_face_package,
    plan_watch_face_transfer,
    plan_original_background_transfer,
    write_original_background_plan,
    write_transfer_plan,
)
from .watchface_store import (
    analyze_store_watch_face_bin,
    download_store_watch_face_bin,
    inspect_store_watch_face_bin,
    plan_store_watch_face_transfer,
    write_store_watch_face_plan,
)
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

    build_face_parser = subparsers.add_parser(
        "build-watch-face",
        help="build an experimental local watch-face image package",
    )
    build_face_parser.add_argument("image", help="source image; PPM works without extra deps")
    build_face_parser.add_argument("--out-dir", required=True, help="output package directory")
    build_face_parser.add_argument("--width", type=int, default=240)
    build_face_parser.add_argument("--height", type=int, default=240)
    build_face_parser.add_argument("--thumb-width", type=int, default=80)
    build_face_parser.add_argument("--thumb-height", type=int, default=80)
    build_face_parser.add_argument(
        "--byteorder",
        choices=["little", "big"],
        default="little",
        help="RGB565 byte order for raw package files",
    )

    face_plan_parser = subparsers.add_parser(
        "watch-face-transfer-plan",
        help="print experimental watch-face transfer packet plan",
    )
    face_plan_parser.add_argument("package_dir", help="directory from build-watch-face")
    face_plan_parser.add_argument("--transfer-type", type=int, default=14)
    face_plan_parser.add_argument(
        "--packet-length",
        type=int,
        help="include wrapped chunk previews for this negotiated file packet length",
    )
    face_plan_parser.add_argument("--chunk-preview-count", type=int, default=1)
    face_plan_parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="plan only the main face file",
    )
    face_plan_parser.add_argument(
        "--name-mode",
        choices=["path", "role"],
        default="path",
        help="filename to place in B7 start packets",
    )
    face_plan_parser.add_argument("--output", help="write plan JSON to a file")

    inspect_face_parser = subparsers.add_parser(
        "inspect-watch-face-package",
        help="validate a generated watch-face image package",
    )
    inspect_face_parser.add_argument("package_dir", help="directory from build-watch-face")

    original_bg_parser = subparsers.add_parser(
        "build-original-background",
        help="build a dry-run ORIGINAL custom-background package",
    )
    original_bg_parser.add_argument("image", help="source image; PPM works without extra deps")
    original_bg_parser.add_argument("--out-dir", required=True, help="output package directory")
    original_bg_parser.add_argument("--width", type=int, default=466)
    original_bg_parser.add_argument("--height", type=int, default=466)

    original_bg_plan_parser = subparsers.add_parser(
        "original-background-transfer-plan",
        help="print a dry-run ORIGINAL custom-background transfer plan",
    )
    original_bg_plan_parser.add_argument("package_dir")
    original_bg_plan_parser.add_argument("--packet-length", type=int, default=256)
    original_bg_plan_parser.add_argument("--chunk-preview-count", type=int, default=2)
    original_bg_plan_parser.add_argument("--output", help="write plan JSON to a file")

    upload_original_bg_parser = subparsers.add_parser(
        "upload-original-background",
        help="guarded experimental upload of an ORIGINAL custom-background package",
    )
    upload_original_bg_parser.add_argument("address")
    upload_original_bg_parser.add_argument("package_dir")
    upload_original_bg_parser.add_argument("--timeout", type=float, default=45.0)
    upload_original_bg_parser.add_argument("--scan-timeout", type=float, default=10.0)
    upload_original_bg_parser.add_argument("--retries", type=int, default=1)
    upload_original_bg_parser.add_argument("--pair", action="store_true")
    upload_original_bg_parser.add_argument("--direct", action="store_true")
    upload_original_bg_parser.add_argument("--wait-timeout", type=float, default=8.0)
    upload_original_bg_parser.add_argument(
        "--packet-length",
        type=int,
        help="override negotiated file packet length",
    )
    upload_original_bg_parser.add_argument("--max-chunks", type=int, default=0)
    upload_original_bg_parser.add_argument(
        "--complete",
        action="store_true",
        help="stream all chunks requested by the watch",
    )
    upload_original_bg_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print transfer plan without connecting",
    )
    upload_original_bg_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this writes custom background state",
    )
    upload_original_bg_parser.add_argument(
        "--experimental-original",
        action="store_true",
        help="acknowledge that ORIGINAL background upload is newly reverse engineered",
    )
    upload_original_bg_parser.add_argument("--json-out", help="write a structured JSON capture")

    download_store_face_parser = subparsers.add_parser(
        "download-watch-face-bin",
        help="download a Da Fit store watch-face .bin file",
    )
    download_store_face_parser.add_argument("url")
    download_store_face_parser.add_argument("--output", required=True)

    inspect_store_face_parser = subparsers.add_parser(
        "inspect-watch-face-bin",
        help="inspect a Da Fit store watch-face .bin file",
    )
    inspect_store_face_parser.add_argument("path")

    analyze_store_face_parser = subparsers.add_parser(
        "analyze-watch-face-bin",
        help="analyze candidate fields inside a Da Fit store watch-face .bin file",
    )
    analyze_store_face_parser.add_argument("path")
    analyze_store_face_parser.add_argument("--scan-limit", type=int, default=4096)

    store_face_plan_parser = subparsers.add_parser(
        "watch-face-bin-transfer-plan",
        help="print a Da Fit store .bin watch-face transfer plan",
    )
    store_face_plan_parser.add_argument("path")
    store_face_plan_parser.add_argument("--packet-length", type=int, default=244)
    store_face_plan_parser.add_argument("--chunk-preview-count", type=int, default=2)
    store_face_plan_parser.add_argument("--output", help="write plan JSON to a file")

    upload_face_parser = subparsers.add_parser(
        "upload-watch-face",
        help="guarded experimental watch-face upload scaffold",
    )
    upload_face_parser.add_argument("address")
    upload_face_parser.add_argument("package_dir", help="directory from build-watch-face")
    upload_face_parser.add_argument("--timeout", type=float, default=45.0)
    upload_face_parser.add_argument("--scan-timeout", type=float, default=10.0)
    upload_face_parser.add_argument("--retries", type=int, default=1)
    upload_face_parser.add_argument("--pair", action="store_true")
    upload_face_parser.add_argument("--direct", action="store_true")
    upload_face_parser.add_argument("--wait-timeout", type=float, default=8.0)
    upload_face_parser.add_argument("--transfer-type", type=int, default=14)
    upload_face_parser.add_argument(
        "--packet-length",
        type=int,
        help="override negotiated file packet length",
    )
    upload_face_parser.add_argument("--chunk-preview-count", type=int, default=1)
    upload_face_parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="plan/upload only the main face file",
    )
    upload_face_parser.add_argument(
        "--name-mode",
        choices=["path", "role"],
        default="path",
        help="filename to place in B7 start packets",
    )
    upload_face_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print transfer plan without connecting",
    )
    upload_face_parser.add_argument(
        "--confirm",
        action="store_true",
        help="allow supervised experimental raw transfer",
    )
    upload_face_parser.add_argument(
        "--experimental-raw",
        action="store_true",
        help="acknowledge that raw RGB565 upload format is unverified",
    )
    upload_face_parser.add_argument(
        "--max-chunks",
        type=int,
        default=0,
        help="send at most this many file chunks unless --complete is used",
    )
    upload_face_parser.add_argument(
        "--complete",
        action="store_true",
        help="stream all chunks requested by the watch",
    )
    upload_face_parser.add_argument("--json-out", help="write a structured JSON capture")

    upload_store_face_parser = subparsers.add_parser(
        "upload-watch-face-bin",
        help="guarded experimental upload of a Da Fit store .bin watch face",
    )
    upload_store_face_parser.add_argument("address")
    upload_store_face_parser.add_argument("path")
    upload_store_face_parser.add_argument("--timeout", type=float, default=45.0)
    upload_store_face_parser.add_argument("--scan-timeout", type=float, default=10.0)
    upload_store_face_parser.add_argument("--retries", type=int, default=1)
    upload_store_face_parser.add_argument("--pair", action="store_true")
    upload_store_face_parser.add_argument("--direct", action="store_true")
    upload_store_face_parser.add_argument("--wait-timeout", type=float, default=8.0)
    upload_store_face_parser.add_argument("--packet-length", type=int, default=244)
    upload_store_face_parser.add_argument("--max-chunks", type=int, default=0)
    upload_store_face_parser.add_argument(
        "--complete",
        action="store_true",
        help="stream all chunks requested by the watch",
    )
    upload_store_face_parser.add_argument(
        "--set-display",
        type=int,
        help="optionally set active watch-face slot after successful upload",
    )
    upload_store_face_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print transfer plan without connecting",
    )
    upload_store_face_parser.add_argument(
        "--confirm",
        action="store_true",
        help="required because this writes a watch-face to the watch",
    )
    upload_store_face_parser.add_argument("--json-out", help="write a structured JSON capture")

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

    export_packets_parser = subparsers.add_parser(
        "export-packets",
        help="export sent/received packet timelines from JSON captures",
    )
    export_packets_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    export_packets_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_packets_parser.add_argument("--output", help="write export to a file instead of stdout")

    packet_summary_parser = subparsers.add_parser(
        "packet-summary",
        help="summarize command counts from packet timelines",
    )
    packet_summary_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    packet_summary_parser.add_argument("--output", help="write summary to a file instead of stdout")
    packet_summary_parser.add_argument("--json", action="store_true", help="write summary JSON")

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

    summary_parser = subparsers.add_parser(
        "summary",
        help="print a compact app-state summary from JSON captures",
    )
    summary_parser.add_argument(
        "paths",
        nargs="*",
        help="capture files or directories; defaults to ble-logs/",
    )
    summary_parser.add_argument("--output", help="write summary to a file instead of stdout")
    summary_parser.add_argument(
        "--json",
        action="store_true",
        help="write machine-readable summary JSON",
    )
    summary_parser.add_argument(
        "--include-samples",
        action="store_true",
        help="include workout sample arrays before summarizing",
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

    import_app_log_parser = subparsers.add_parser(
        "import-app-log",
        help="extract Da Fit app BLE log bytes into a clean-room capture",
    )
    import_app_log_parser.add_argument(
        "paths",
        nargs="+",
        help="Da Fit moy_logs files or directories",
    )
    import_app_log_parser.add_argument("--output", help="write JSON capture to this file")
    import_app_log_parser.add_argument(
        "--out-dir",
        help="write reconstructed transfer payload files to this directory",
    )
    import_app_log_parser.add_argument(
        "--no-data",
        action="store_true",
        help="omit byte hex dumps from JSON; summaries are still included",
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
    elif args.command == "build-watch-face":
        try:
            manifest = build_watch_face_package(
                args.image,
                args.out_dir,
                width=args.width,
                height=args.height,
                thumb_width=args.thumb_width,
                thumb_height=args.thumb_height,
                byteorder=args.byteorder,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            parser.error(str(exc))
        print(f"wrote watch-face package: {args.out_dir}")
        for file_info in manifest["files"]:
            print(
                f"  {file_info['role']}: {file_info['path']} "
                f"{file_info['size']} bytes sha256={file_info['sha256'][:12]}"
            )
    elif args.command == "watch-face-transfer-plan":
        try:
            plan = plan_watch_face_transfer(
                args.package_dir,
                transfer_type=args.transfer_type,
                include_thumbnail=not args.no_thumbnail,
                packet_length=args.packet_length,
                chunk_preview_count=args.chunk_preview_count,
                name_mode=args.name_mode,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        write_transfer_plan(plan, output=args.output)
    elif args.command == "inspect-watch-face-package":
        try:
            inspection = inspect_watch_face_package(args.package_dir)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        print(json.dumps(inspection, indent=2, sort_keys=True))
    elif args.command == "build-original-background":
        try:
            manifest = build_original_background_package(
                args.image,
                args.out_dir,
                width=args.width,
                height=args.height,
            )
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(f"wrote original background package: {args.out_dir}")
        print(json.dumps(manifest, indent=2, sort_keys=True))
    elif args.command == "original-background-transfer-plan":
        try:
            plan = plan_original_background_transfer(
                args.package_dir,
                packet_length=args.packet_length,
                chunk_preview_count=args.chunk_preview_count,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        write_original_background_plan(plan, output=args.output)
    elif args.command == "upload-original-background":
        try:
            plan = plan_original_background_transfer(
                args.package_dir,
                packet_length=args.packet_length or 64,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.dry_run:
            write_original_background_plan(plan)
            return
        if not args.confirm or not args.experimental_original:
            parser.error(
                "upload-original-background changes watch state; "
                "rerun with --confirm --experimental-original after reviewing --dry-run"
            )
        if args.complete is False and args.max_chunks == 0:
            print("handshake-only mode: will stop after the first transfer event")
        asyncio.run(
            upload_original_background(
                args.address,
                args.package_dir,
                packet_length=args.packet_length,
                max_chunks=args.max_chunks,
                complete=args.complete,
                wait_timeout=args.wait_timeout,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )
    elif args.command == "download-watch-face-bin":
        try:
            info = download_store_watch_face_bin(args.url, args.output)
        except OSError as exc:
            parser.error(str(exc))
        print(json.dumps(info, indent=2, sort_keys=True))
    elif args.command == "inspect-watch-face-bin":
        try:
            inspection = inspect_store_watch_face_bin(args.path)
        except OSError as exc:
            parser.error(str(exc))
        print(json.dumps(inspection, indent=2, sort_keys=True))
    elif args.command == "analyze-watch-face-bin":
        try:
            analysis = analyze_store_watch_face_bin(args.path, scan_limit=args.scan_limit)
        except OSError as exc:
            parser.error(str(exc))
        print(json.dumps(analysis, indent=2, sort_keys=True))
    elif args.command == "watch-face-bin-transfer-plan":
        try:
            plan = plan_store_watch_face_transfer(
                args.path,
                packet_length=args.packet_length,
                chunk_preview_count=args.chunk_preview_count,
            )
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        write_store_watch_face_plan(plan, output=args.output)
    elif args.command == "upload-watch-face":
        try:
            plan = plan_watch_face_transfer(
                args.package_dir,
                transfer_type=args.transfer_type,
                include_thumbnail=not args.no_thumbnail,
                packet_length=args.packet_length,
                chunk_preview_count=args.chunk_preview_count,
                name_mode=args.name_mode,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.dry_run:
            write_transfer_plan(plan)
            return
        if not args.confirm or not args.experimental_raw:
            parser.error(
                "real watch-face upload is experimental and state-changing; "
                "rerun with --confirm --experimental-raw after reviewing --dry-run"
            )
        asyncio.run(
            upload_watch_face_raw(
                args.address,
                args.package_dir,
                transfer_type=args.transfer_type,
                packet_length=args.packet_length,
                include_thumbnail=not args.no_thumbnail,
                name_mode=args.name_mode,
                max_chunks=args.max_chunks,
                complete=args.complete,
                wait_timeout=args.wait_timeout,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
                json_out=args.json_out,
            )
        )
    elif args.command == "upload-watch-face-bin":
        try:
            plan = plan_store_watch_face_transfer(args.path, packet_length=args.packet_length)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        if args.dry_run:
            write_store_watch_face_plan(plan)
            return
        if not args.confirm:
            parser.error("upload-watch-face-bin changes watch state; rerun with --confirm")
        if args.complete is False and args.max_chunks == 0:
            print("running handshake-only upload; use --max-chunks N or --complete to stream data")
        asyncio.run(
            upload_store_watch_face(
                args.address,
                args.path,
                packet_length=args.packet_length,
                max_chunks=args.max_chunks,
                complete=args.complete,
                wait_timeout=args.wait_timeout,
                set_display=args.set_display,
                timeout=args.timeout,
                scan_timeout=args.scan_timeout,
                retries=args.retries,
                pair=args.pair,
                direct=args.direct,
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
    elif args.command == "export-packets":
        events = load_packet_events(args.paths)
        write_packet_events(events, args.format, output=args.output)
    elif args.command == "packet-summary":
        events = load_packet_events(args.paths)
        summary = summarize_packet_events(events)
        write_packet_summary(summary, output=args.output, json_output=args.json)
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
    elif args.command == "summary":
        state = load_app_state(args.paths, include_samples=args.include_samples)
        summary = summarize_app_state(state)
        write_app_state_summary(summary, output=args.output, json_output=args.json)
    elif args.command == "tui":
        run_capture_tui(args.paths)
    elif args.command == "import-app-log":
        capture = import_app_logs(args.paths, include_data=not args.no_data)
        write_imported_app_log(capture, output=args.output, out_dir=args.out_dir)
        if args.output or args.out_dir:
            summary = capture["summary"]
            print(
                "imported app log: "
                f"{summary['events']} events, "
                f"{summary['transfer_chunks']} transfer chunks, "
                f"{summary['transfer_payload_size']} transfer bytes"
            )


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

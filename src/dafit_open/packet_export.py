"""Packet timeline exports from dafit-open captures."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any, TextIO

from .protocol import decode_frame, hex_bytes, parse_frame


PACKET_CSV_FIELDS = [
    "source",
    "order",
    "timestamp",
    "direction",
    "kind",
    "channel",
    "command",
    "command_hex",
    "payload_len",
    "payload_hex",
    "frame_hex",
    "decoded",
]


def load_packet_events(paths: list[str | Path] | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    order = 0
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for item in _capture_packet_events(capture, path, order):
            order += 1
            item["order"] = order
            events.append(item)
    events.sort(key=lambda event: _sort_key(event))
    for index, event in enumerate(events, start=1):
        event["order"] = index
    return events


def write_packet_events(
    events: list[dict[str, Any]],
    fmt: str,
    output: str | Path | None = None,
) -> None:
    stream: TextIO
    should_close = False
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stream = output_path.open("w", newline="")
        should_close = True
    else:
        stream = sys.stdout
    try:
        if fmt == "json":
            json.dump(events, stream, indent=2, sort_keys=True)
            stream.write("\n")
        elif fmt == "csv":
            writer = csv.DictWriter(stream, fieldnames=PACKET_CSV_FIELDS)
            writer.writeheader()
            for event in events:
                writer.writerow({field: event.get(field) for field in PACKET_CSV_FIELDS})
        else:
            raise ValueError(f"unknown packet export format: {fmt}")
    finally:
        if should_close:
            stream.close()


def _capture_packet_events(
    capture: dict[str, Any],
    source: Path,
    order_start: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    order = order_start
    for packet in capture.get("sent_packets", []):
        order += 1
        events.append(_sent_packet_event(packet, source, order))
    for notification in capture.get("notifications", []):
        order += 1
        events.append(_notification_event(notification, source, order))
    for app_event in capture.get("events", []):
        if not isinstance(app_event, dict) or "frame" not in app_event:
            continue
        order += 1
        events.append(_app_log_event(app_event, source, order))
    return events


def _sent_packet_event(packet: dict[str, Any], source: Path, order: int) -> dict[str, Any]:
    raw = _bytes_from_hex(str(packet.get("hex", "")))
    frame = parse_frame(raw) if raw else None
    command = packet.get("command")
    payload_hex = str(packet.get("payload_hex") or "")
    return _event(
        source=source,
        order=order,
        timestamp=packet.get("timestamp"),
        direction="tx",
        kind="sent_packet",
        channel=packet.get("channel"),
        command=int(command) if isinstance(command, int) else (frame.command if frame else None),
        payload_hex=payload_hex,
        frame_hex=hex_bytes(raw) if raw else str(packet.get("hex") or ""),
        frame=frame,
    )


def _notification_event(notification: dict[str, Any], source: Path, order: int) -> dict[str, Any]:
    frame_data = notification.get("frame") or {}
    raw = _bytes_from_hex(str(frame_data.get("hex") or notification.get("hex") or ""))
    frame = parse_frame(raw) if raw else None
    command = frame.command if frame else frame_data.get("command")
    payload_hex = (
        hex_bytes(frame.payload)
        if frame
        else str(frame_data.get("payload_hex") or "")
    )
    event = _event(
        source=source,
        order=order,
        timestamp=notification.get("timestamp"),
        direction="rx",
        kind="notification",
        channel=str((notification.get("characteristic") or {}).get("uuid") or ""),
        command=int(command) if isinstance(command, int) else None,
        payload_hex=payload_hex,
        frame_hex=hex_bytes(raw) if raw else str(frame_data.get("hex") or notification.get("hex") or ""),
        frame=frame,
    )
    if not event.get("decoded") and frame_data.get("decoded"):
        event["decoded"] = frame_data["decoded"]
    return event


def _app_log_event(app_event: dict[str, Any], source: Path, order: int) -> dict[str, Any]:
    frame_data = app_event.get("frame") or {}
    payload_hex = str(frame_data.get("payload_hex") or "")
    command = frame_data.get("command")
    data_hex = str(app_event.get("data_hex") or "")
    raw = _bytes_from_hex(data_hex)
    frame = parse_frame(raw) if raw else None
    kind = str(app_event.get("kind") or "app_log_frame")
    return _event(
        source=source,
        order=order,
        timestamp=app_event.get("timestamp"),
        direction="rx" if kind.startswith("rx") else "tx",
        kind=kind,
        channel=None,
        command=int(command) if isinstance(command, int) else (frame.command if frame else None),
        payload_hex=payload_hex,
        frame_hex=hex_bytes(raw) if raw else "",
        frame=frame,
    )


def _event(
    source: Path,
    order: int,
    timestamp: object,
    direction: str,
    kind: str,
    channel: object,
    command: int | None,
    payload_hex: str,
    frame_hex: str,
    frame: object,
) -> dict[str, Any]:
    decoded = decode_frame(frame) if frame is not None else None
    payload_len = len(_bytes_from_hex(payload_hex))
    return {
        "source": str(source),
        "order": order,
        "timestamp": timestamp,
        "direction": direction,
        "kind": kind,
        "channel": channel,
        "command": command,
        "command_hex": f"0x{command:02X}" if command is not None else None,
        "payload_len": payload_len,
        "payload_hex": payload_hex,
        "frame_hex": frame_hex,
        "decoded": decoded,
    }


def _resolve_capture_paths(paths: list[str | Path] | None) -> list[Path]:
    if not paths:
        paths = [Path("ble-logs")]
    resolved: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            resolved.extend(sorted(path.glob("*.json")))
        elif any(char in str(path) for char in "*?[]"):
            resolved.extend(sorted(Path().glob(str(path))))
        else:
            resolved.append(path)
    return resolved


def _bytes_from_hex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def _sort_key(event: dict[str, Any]) -> tuple[str, int]:
    timestamp = event.get("timestamp")
    if timestamp is None:
        return ("~", int(event.get("order", 0)))
    return (str(timestamp), int(event.get("order", 0)))

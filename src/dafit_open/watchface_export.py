"""Structured watch-face exports from JSON captures."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO

from .protocol import (
    parse_display_watch_face,
    parse_frame,
    parse_support_watch_faces,
    parse_watch_face_list,
    parse_watch_face_screen,
)


def load_watch_face_state(paths: list[str | Path] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "device_version": None,
        "display_slot": None,
        "slots": [],
        "support": None,
        "screen": None,
        "sources": [],
    }
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(capture.get("watch_faces"), dict):
            _merge_explicit_state(state, capture["watch_faces"], path)
        for notification in capture.get("notifications", []):
            frame_data = notification.get("frame") or {}
            raw = _frame_raw_bytes(frame_data)
            frame = parse_frame(raw) if raw else None
            if frame is None:
                command = frame_data.get("command")
                payload = _bytes_from_hex(frame_data.get("payload_hex", ""))
            else:
                command = frame.command
                payload = frame.payload
            _merge_frame(state, command, payload, path)
    return state


def write_watch_face_export(state: dict[str, Any], output: str | Path | None = None) -> None:
    stream: TextIO
    should_close = False
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stream = output_path.open("w")
        should_close = True
    else:
        stream = sys.stdout
    try:
        json.dump(state, stream, indent=2, sort_keys=True)
        stream.write("\n")
    finally:
        if should_close:
            stream.close()


def _merge_explicit_state(state: dict[str, Any], watch_faces: dict[str, Any], source: Path) -> None:
    for key in ("device_version", "display_slot", "support", "screen"):
        if watch_faces.get(key) is not None:
            state[key] = watch_faces[key]
    if watch_faces.get("slots"):
        state["slots"] = watch_faces["slots"]
    _append_source(state, source)


def _merge_frame(state: dict[str, Any], command: int | None, payload: bytes, source: Path) -> None:
    if command == 0x2E and payload:
        state["device_version"] = payload[0]
    elif command == 0x29:
        display_slot = parse_display_watch_face(payload)
        if display_slot is not None:
            state["display_slot"] = display_slot
    elif command == 0xA6:
        slots = parse_watch_face_list(payload)
        if slots is not None:
            state["slots"] = [slot.to_dict() for slot in slots]
    elif command == 0x84:
        support = parse_support_watch_faces(payload)
        if support is not None:
            state["support"] = support.to_dict()
    elif command == 0xB4:
        screen = parse_watch_face_screen(payload)
        if screen is not None:
            state["screen"] = screen.to_dict()
    else:
        return
    _append_source(state, source)


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


def _append_source(state: dict[str, Any], source: Path) -> None:
    value = str(source)
    if value not in state["sources"]:
        state["sources"].append(value)


def _frame_raw_bytes(frame_data: dict[str, Any]) -> bytes:
    raw = _bytes_from_hex(frame_data.get("hex", ""))
    if raw:
        return raw
    return b""


def _bytes_from_hex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""

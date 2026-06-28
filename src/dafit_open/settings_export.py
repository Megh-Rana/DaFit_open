"""Structured settings exports from JSON captures."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO


def load_settings_state(paths: list[str | Path] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "goal_steps": None,
        "time_system": None,
        "display_time_enabled": None,
        "do_not_disturb": None,
        "sources": [],
    }
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for notification in capture.get("notifications", []):
            frame = notification.get("frame") or {}
            command = frame.get("command")
            payload = _bytes_from_hex(frame.get("payload_hex", ""))
            _merge_settings_payload(state, command, payload, path)
    return state


def write_settings_export(state: dict[str, Any], output: str | Path | None = None) -> None:
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


def _merge_settings_payload(
    state: dict[str, Any],
    command: int | None,
    payload: bytes,
    source: Path,
) -> None:
    if command == 0x26 and len(payload) >= 4:
        state["goal_steps"] = int.from_bytes(payload[:4], "little")
    elif command == 0x27 and payload:
        state["time_system"] = payload[0]
    elif command == 0x28 and payload:
        state["display_time_enabled"] = payload[0] == 1
    elif command == 0x81 and len(payload) >= 4:
        state["do_not_disturb"] = {
            "start_hour": payload[0],
            "start_minute": payload[1],
            "end_hour": payload[2],
            "end_minute": payload[3],
        }
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


def _bytes_from_hex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""

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
        "dominant_hand": None,
        "metric_system": None,
        "display_time": None,
        "quick_view_enabled": None,
        "quick_view_time": None,
        "sedentary_reminder_enabled": None,
        "sedentary_reminder_period": None,
        "drink_water_reminder": None,
        "new_drink_water_reminder": None,
        "hand_washing_reminder": None,
        "screen_off_clock_enabled": None,
        "screen_off_clock_time": None,
        "tap_to_wake_enabled": None,
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
        state["quick_view_enabled"] = payload[0] == 1
    elif command == 0x81 and len(payload) >= 4:
        state["do_not_disturb"] = {
            "start_hour": payload[0],
            "start_minute": payload[1],
            "end_hour": payload[2],
            "end_minute": payload[3],
        }
    elif command == 0x24 and payload:
        state["dominant_hand"] = payload[0]
    elif command == 0x2A and payload:
        state["metric_system"] = payload[0]
    elif command == 0x2D and payload:
        state["sedentary_reminder_enabled"] = payload[0] == 1
    elif command == 0x82 and len(payload) >= 4:
        state["quick_view_time"] = _period_dict(payload)
    elif command == 0x83 and len(payload) >= 4:
        state["sedentary_reminder_period"] = {
            "period": payload[0],
            "steps": payload[1],
            "start_hour": payload[2],
            "end_hour": payload[3],
        }
    elif command == 0x87 and payload:
        _merge_reminder_period(state, payload)
    elif command == 0x8D and payload:
        state["display_time"] = payload[0]
    elif command == 0xAC and payload:
        state["tap_to_wake_enabled"] = payload[0] == 1
    elif command == 0xBB and len(payload) >= 2:
        _merge_bb_settings(state, payload)
    else:
        return
    _append_source(state, source)


def _period_dict(payload: bytes) -> dict[str, int]:
    return {
        "start_hour": payload[0],
        "start_minute": payload[1],
        "end_hour": payload[2],
        "end_minute": payload[3],
    }


def _merge_reminder_period(state: dict[str, Any], payload: bytes) -> None:
    labels = {
        1: "drink_water_reminder",
        3: "hand_washing_reminder",
    }
    label = labels.get(payload[0])
    if label is None:
        return
    if len(payload) >= 6:
        state[label] = {
            "enabled": payload[1] == 1,
            "start_hour": payload[2],
            "start_minute": payload[3],
            "count": payload[4],
            "period": payload[5],
        }
    else:
        state[label] = {"raw_hex": payload.hex(" ").upper()}


def _merge_bb_settings(state: dict[str, Any], payload: bytes) -> None:
    group = payload[0]
    subcommand = payload[1]
    data = payload[2:]
    if group == 4 and subcommand == 6:
        if len(data) >= 6:
            state["new_drink_water_reminder"] = {
                "enabled": data[1] == 1,
                "start_hour": data[2],
                "start_minute": data[3],
                "count": data[4],
                "period": data[5],
            }
        else:
            state["new_drink_water_reminder"] = {"raw_hex": payload.hex(" ").upper()}
    elif group == 12 and subcommand == 0:
        if data:
            state["screen_off_clock_enabled"] = data[0] == 1
        else:
            state["screen_off_clock_enabled"] = None
    elif group == 12 and subcommand == 2:
        if len(data) >= 4:
            state["screen_off_clock_time"] = _period_dict(data)
        else:
            state["screen_off_clock_time"] = {"raw_hex": payload.hex(" ").upper()}


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

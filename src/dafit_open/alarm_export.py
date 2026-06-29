"""Structured alarm exports from JSON captures."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO

from .protocol import parse_alarm_list, parse_new_alarm_list


def load_alarm_state(paths: list[str | Path] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "legacy_alarms": [],
        "new_alarms": [],
        "sources": [],
    }
    seen_legacy: set[tuple[Any, ...]] = set()
    seen_new: set[tuple[Any, ...]] = set()
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for notification in capture.get("notifications", []):
            frame = notification.get("frame") or {}
            command = frame.get("command")
            payload = _bytes_from_hex(frame.get("payload_hex", ""))
            if command == 0x21:
                alarms = parse_alarm_list(payload)
                if alarms is not None:
                    _merge_alarms(state["legacy_alarms"], alarms, seen_legacy)
                    _append_source(state, path)
            elif command == 0xB9:
                alarms = parse_new_alarm_list(payload)
                if alarms is not None:
                    _merge_alarms(state["new_alarms"], alarms, seen_new)
                    _append_source(state, path)
    return state


def write_alarm_export(state: dict[str, Any], output: str | Path | None = None) -> None:
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


def _merge_alarms(target: list[dict[str, Any]], alarms: list[Any], seen: set[tuple[Any, ...]]) -> None:
    for alarm in alarms:
        data = alarm.to_dict()
        key = (
            data["id"],
            data["enabled"],
            data["hour"],
            data["minute"],
            data["repeat_mode"],
            data["date"],
        )
        if key in seen:
            continue
        seen.add(key)
        target.append(data)


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

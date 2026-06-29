"""Aggregate app-ready state from captured watch data."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO

from .alarm_export import load_alarm_state
from .capture_export import load_workout_summaries
from .settings_export import load_settings_state
from .watchface_export import load_watch_face_state


DEVICE_FIELD_UUIDS = {
    "00002a00-0000-1000-8000-00805f9b34fb": "name",
    "00002a01-0000-1000-8000-00805f9b34fb": "appearance",
    "00002a19-0000-1000-8000-00805f9b34fb": "battery_level",
    "00002a24-0000-1000-8000-00805f9b34fb": "model_number",
    "00002a25-0000-1000-8000-00805f9b34fb": "serial_number",
    "00002a26-0000-1000-8000-00805f9b34fb": "firmware_revision",
    "00002a27-0000-1000-8000-00805f9b34fb": "hardware_revision",
    "00002a28-0000-1000-8000-00805f9b34fb": "software_revision",
    "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer_name",
    "00002a50-0000-1000-8000-00805f9b34fb": "pnp_id",
}


def load_app_state(
    paths: list[str | Path] | None = None,
    include_samples: bool = False,
) -> dict[str, Any]:
    capture_paths = _resolve_capture_paths(paths)
    return {
        "schema": "dafit-open.app-state.v1",
        "alarms": load_alarm_state(capture_paths),
        "device": load_device_profile(capture_paths),
        "settings": load_settings_state(capture_paths),
        "watch_faces": load_watch_face_state(capture_paths),
        "workouts": [
            workout.to_dict(include_samples=include_samples)
            for workout in load_workout_summaries(capture_paths)
        ],
    }


def load_device_profile(paths: list[str | Path] | None = None) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "address": None,
        "name": None,
        "fields": {},
        "services": [],
        "sources": [],
    }
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if capture.get("address"):
            profile["address"] = capture["address"]
        device = capture.get("device")
        if isinstance(device, dict):
            if device.get("address"):
                profile["address"] = device["address"]
            if device.get("name"):
                profile["name"] = device["name"]
        if capture.get("services"):
            profile["services"] = capture["services"]
            _append_source(profile, path)
        for read in capture.get("reads", []):
            _merge_read(profile, read, path)
    return profile


def write_app_state(state: dict[str, Any], output: str | Path | None = None) -> None:
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


def _merge_read(profile: dict[str, Any], read: dict[str, Any], source: Path) -> None:
    if not read.get("ok"):
        return
    characteristic = read.get("characteristic") or {}
    uuid = str(characteristic.get("uuid", "")).lower()
    field_name = DEVICE_FIELD_UUIDS.get(uuid)
    value = read.get("value") or {}
    if field_name:
        profile["fields"][field_name] = _field_value(value)
        if field_name == "name" and value.get("value"):
            profile["name"] = value["value"]
    profile["fields"][uuid] = {
        "name": characteristic.get("name"),
        "value": _field_value(value),
        "type": value.get("type"),
        "hex": value.get("hex"),
    }
    _append_source(profile, source)


def _field_value(value: dict[str, Any]) -> Any:
    if "value" in value:
        return value["value"]
    if "hex" in value:
        return value["hex"]
    return value


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


def _append_source(profile: dict[str, Any], source: Path) -> None:
    value = str(source)
    if value not in profile["sources"]:
        profile["sources"].append(value)

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


def summarize_app_state(state: dict[str, Any]) -> dict[str, Any]:
    device = _as_dict(state.get("device"))
    fields = _as_dict(device.get("fields"))
    watch_faces = _as_dict(state.get("watch_faces"))
    settings = _as_dict(state.get("settings"))
    alarms = _as_dict(state.get("alarms"))
    workouts = state.get("workouts") if isinstance(state.get("workouts"), list) else []
    slots = watch_faces.get("slots") if isinstance(watch_faces.get("slots"), list) else []
    support = _as_dict(watch_faces.get("support"))
    legacy_alarms = alarms.get("legacy_alarms") if isinstance(alarms.get("legacy_alarms"), list) else []
    new_alarms = alarms.get("new_alarms") if isinstance(alarms.get("new_alarms"), list) else []

    return {
        "schema": "dafit-open.app-state-summary.v1",
        "device": {
            "name": device.get("name"),
            "address": device.get("address"),
            "battery_level": fields.get("battery_level"),
            "model_number": fields.get("model_number"),
            "firmware_revision": fields.get("firmware_revision"),
        },
        "watch_faces": {
            "display_slot": watch_faces.get("display_slot"),
            "slot_count": len(slots),
            "slot_types": _count_slot_types(slots),
            "support_display_index": support.get("display_index"),
            "supported": support.get("supported") if isinstance(support.get("supported"), list) else [],
        },
        "settings": {
            "known_count": _known_settings_count(settings),
            "goal_steps": settings.get("goal_steps"),
            "display_time_enabled": settings.get("display_time_enabled"),
            "quick_view_enabled": settings.get("quick_view_enabled"),
            "time_system": settings.get("time_system"),
        },
        "alarms": {
            "legacy_count": len(legacy_alarms),
            "new_count": len(new_alarms),
            "enabled_count": _enabled_alarm_count(legacy_alarms) + _enabled_alarm_count(new_alarms),
        },
        "workouts": {
            "count": len(workouts),
            "with_heart_rate": _workouts_with_series(workouts, "heart_rate"),
            "with_steps": _workouts_with_series(workouts, "steps_series"),
            "with_distance": _workouts_with_series(workouts, "distance_series"),
        },
    }


def format_app_state_summary(summary: dict[str, Any]) -> list[str]:
    device = _as_dict(summary.get("device"))
    watch_faces = _as_dict(summary.get("watch_faces"))
    settings = _as_dict(summary.get("settings"))
    alarms = _as_dict(summary.get("alarms"))
    workouts = _as_dict(summary.get("workouts"))
    return [
        "App State Summary",
        "",
        f"Device       : {_value(device.get('name'))} ({_value(device.get('address'))})",
        f"Battery      : {_percent(device.get('battery_level'))}",
        f"Model        : {_value(device.get('model_number'))}",
        f"Firmware     : {_value(device.get('firmware_revision'))}",
        "",
        f"Watch face   : display={_value(watch_faces.get('display_slot'))}, "
        f"slots={watch_faces.get('slot_count', 0)}, types={_slot_types_display(watch_faces.get('slot_types'))}",
        f"Support      : display_index={_value(watch_faces.get('support_display_index'))}, "
        f"supported={_list_display(watch_faces.get('supported'))}",
        "",
        f"Settings     : {settings.get('known_count', 0)} known, "
        f"goal={_value(settings.get('goal_steps'))}, "
        f"quick_view={_value(settings.get('quick_view_enabled'))}",
        f"Alarms       : legacy={alarms.get('legacy_count', 0)}, "
        f"new={alarms.get('new_count', 0)}, enabled={alarms.get('enabled_count', 0)}",
        f"Workouts     : {workouts.get('count', 0)} total, "
        f"hr={workouts.get('with_heart_rate', 0)}, "
        f"steps={workouts.get('with_steps', 0)}, "
        f"distance={workouts.get('with_distance', 0)}",
    ]


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


def write_app_state_summary(
    summary: dict[str, Any],
    output: str | Path | None = None,
    json_output: bool = False,
) -> None:
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
        if json_output:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write("\n")
        else:
            stream.write("\n".join(format_app_state_summary(summary)))
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


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count_slot_types(slots: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        slot_type = str(slot.get("kind") or slot.get("type") or "?")
        counts[slot_type] = counts.get(slot_type, 0) + 1
    return counts


def _known_settings_count(settings: dict[str, Any]) -> int:
    return sum(1 for key, value in settings.items() if key != "sources" and value is not None)


def _enabled_alarm_count(alarms: list[Any]) -> int:
    return sum(1 for alarm in alarms if isinstance(alarm, dict) and bool(alarm.get("enabled")))


def _workouts_with_series(workouts: list[Any], key: str) -> int:
    count = 0
    for workout in workouts:
        if not isinstance(workout, dict):
            continue
        series = workout.get(key)
        if isinstance(series, dict) and series.get("values"):
            count += 1
    return count


def _value(value: Any) -> str:
    return "-" if value is None else str(value)


def _percent(value: Any) -> str:
    if value is None:
        return "-"
    return f"{value}%"


def _slot_types_display(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "-"
    return ",".join(f"{key}:{value[key]}" for key in sorted(value))


def _list_display(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    return ",".join(str(item) for item in value)

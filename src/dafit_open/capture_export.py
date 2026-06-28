"""Structured exports from dafit-open JSON captures."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, TextIO


TRAINING_SERIES_NAMES = {
    0x05: "heart_rate",
    0x08: "steps",
    0x0A: "distance",
}


@dataclass
class SeriesData:
    values: list[int] = field(default_factory=list)
    chunks: int = 0
    complete: bool = False
    next_offsets: list[int] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    seen_chunk_keys: set[str] = field(default_factory=set, repr=False)

    @property
    def nonzero_count(self) -> int:
        return sum(1 for value in self.values if value != 0)

    @property
    def trimmed_values(self) -> list[int]:
        values = list(self.values)
        while values and values[-1] == 0:
            values.pop()
        return values


@dataclass
class WorkoutSummary:
    id: int
    type: int | None = None
    listed_start: str | None = None
    start: str | None = None
    end: str | None = None
    valid_time: int | None = None
    steps: int | None = None
    distance: int | None = None
    calories: int | None = None
    heart_rate: SeriesData = field(default_factory=SeriesData)
    steps_series: SeriesData = field(default_factory=SeriesData)
    distance_series: SeriesData = field(default_factory=SeriesData)
    sources: list[str] = field(default_factory=list)

    def to_dict(self, include_samples: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "listed_start": self.listed_start,
            "start": self.start,
            "end": self.end,
            "valid_time": self.valid_time,
            "steps": self.steps,
            "distance": self.distance,
            "calories": self.calories,
            "heart_rate": _series_to_dict(self.heart_rate, include_samples),
            "steps_series": _series_to_dict(self.steps_series, include_samples),
            "distance_series": _series_to_dict(self.distance_series, include_samples),
            "sources": sorted(set(self.sources)),
        }
        return {key: value for key, value in result.items() if value is not None}


def load_workout_summaries(paths: list[str | Path] | None = None) -> list[WorkoutSummary]:
    workouts: dict[int, WorkoutSummary] = {}
    for path in _resolve_capture_paths(paths):
        try:
            capture = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for notification in capture.get("notifications", []):
            frame = notification.get("frame") or {}
            if frame.get("command") != 0xB2:
                continue
            payload = _bytes_from_hex(frame.get("payload_hex", ""))
            if not payload:
                continue
            _merge_training_payload(workouts, payload, path)
    return [workouts[workout_id] for workout_id in sorted(workouts)]


def write_workout_export(
    workouts: list[WorkoutSummary],
    fmt: str,
    output: str | Path | None = None,
    include_samples: bool = True,
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
            data = [workout.to_dict(include_samples=include_samples) for workout in workouts]
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        elif fmt == "csv":
            _write_workout_csv(workouts, stream)
        else:
            raise ValueError(f"unknown export format: {fmt}")
    finally:
        if should_close:
            stream.close()


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


def _merge_training_payload(workouts: dict[int, WorkoutSummary], payload: bytes, source: Path) -> None:
    subcommand = payload[0]
    if subcommand == 0x01:
        _merge_training_list(workouts, payload, source)
    elif subcommand == 0x03:
        _merge_training_detail(workouts, payload, source)
    elif subcommand in TRAINING_SERIES_NAMES:
        _merge_training_series(workouts, payload, source)


def _merge_training_list(workouts: dict[int, WorkoutSummary], payload: bytes, source: Path) -> None:
    if len(payload) % 5 != 1:
        return
    for offset in range(1, len(payload), 5):
        timestamp = int.from_bytes(payload[offset : offset + 4], "little")
        if timestamp <= 1:
            continue
        workout_id = offset // 5
        workout = _workout(workouts, workout_id)
        workout.type = payload[offset + 4]
        workout.listed_start = _format_timestamp(timestamp)
        _append_source(workout.sources, source)


def _merge_training_detail(workouts: dict[int, WorkoutSummary], payload: bytes, source: Path) -> None:
    if len(payload) < 26:
        return
    workout = _workout(workouts, payload[1])
    workout.start = _format_timestamp(int.from_bytes(payload[2:6], "little"))
    workout.end = _format_timestamp(int.from_bytes(payload[6:10], "little"))
    workout.valid_time = int.from_bytes(payload[10:12], "little")
    workout.type = payload[13]
    workout.steps = int.from_bytes(payload[14:18], "little")
    workout.distance = int.from_bytes(payload[18:22], "little")
    workout.calories = int.from_bytes(payload[22:24], "little")
    _append_source(workout.sources, source)


def _merge_training_series(workouts: dict[int, WorkoutSummary], payload: bytes, source: Path) -> None:
    if len(payload) < 4:
        return
    workout = _workout(workouts, payload[1])
    series = _series_for(workout, payload[0])
    data = payload[4:]
    if payload[0] == 0x05:
        values = [value if 40 <= value <= 200 else 0 for value in data]
    elif payload[0] == 0x0A:
        if len(data) % 2 != 0:
            return
        values = [int.from_bytes(data[index : index + 2], "little") for index in range(0, len(data), 2)]
    else:
        values = list(data)
    next_offset = int.from_bytes(payload[2:4], "big")
    chunk_key = payload.hex()
    if chunk_key in series.seen_chunk_keys:
        _append_source(series.sources, source)
        _append_source(workout.sources, source)
        return
    series.seen_chunk_keys.add(chunk_key)
    series.values.extend(values)
    series.chunks += 1
    series.next_offsets.append(next_offset)
    series.complete = series.complete or next_offset == 0xFFFF
    _append_source(series.sources, source)
    _append_source(workout.sources, source)


def _series_for(workout: WorkoutSummary, subcommand: int) -> SeriesData:
    if subcommand == 0x05:
        return workout.heart_rate
    if subcommand == 0x08:
        return workout.steps_series
    if subcommand == 0x0A:
        return workout.distance_series
    raise ValueError(f"unsupported training series response: 0x{subcommand:02X}")


def _workout(workouts: dict[int, WorkoutSummary], workout_id: int) -> WorkoutSummary:
    if workout_id not in workouts:
        workouts[workout_id] = WorkoutSummary(id=workout_id)
    return workouts[workout_id]


def _append_source(sources: list[str], source: Path) -> None:
    value = str(source)
    if value not in sources:
        sources.append(value)


def _bytes_from_hex(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def _format_timestamp(timestamp: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def _series_to_dict(series: SeriesData, include_samples: bool) -> dict[str, Any]:
    trimmed = series.trimmed_values
    result: dict[str, Any] = {
        "count": len(series.values),
        "nonzero_count": series.nonzero_count,
        "trimmed_count": len(trimmed),
        "chunks": series.chunks,
        "complete": series.complete,
        "next_offsets": series.next_offsets,
        "sources": sorted(set(series.sources)),
    }
    if include_samples:
        result["values"] = trimmed
    return result


def _write_workout_csv(workouts: list[WorkoutSummary], stream: TextIO) -> None:
    fieldnames = [
        "id",
        "type",
        "listed_start",
        "start",
        "end",
        "valid_time",
        "steps",
        "distance",
        "calories",
        "heart_rate_count",
        "heart_rate_trimmed_count",
        "heart_rate_nonzero_count",
        "heart_rate_chunks",
        "heart_rate_complete",
        "steps_series_count",
        "distance_series_count",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for workout in workouts:
        writer.writerow(
            {
                "id": workout.id,
                "type": workout.type,
                "listed_start": workout.listed_start,
                "start": workout.start,
                "end": workout.end,
                "valid_time": workout.valid_time,
                "steps": workout.steps,
                "distance": workout.distance,
                "calories": workout.calories,
                "heart_rate_count": len(workout.heart_rate.values),
                "heart_rate_trimmed_count": len(workout.heart_rate.trimmed_values),
                "heart_rate_nonzero_count": workout.heart_rate.nonzero_count,
                "heart_rate_chunks": workout.heart_rate.chunks,
                "heart_rate_complete": workout.heart_rate.complete,
                "steps_series_count": len(workout.steps_series.values),
                "distance_series_count": len(workout.distance_series.values),
            }
        )

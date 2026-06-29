"""Read-only terminal UI for browsing captured app/watch data."""

from __future__ import annotations

import curses
from pathlib import Path
import textwrap
from typing import Sequence

from .capture_export import WorkoutSummary, load_workout_summaries
from .state_export import load_app_state


def run_capture_tui(paths: Sequence[str | Path] | None = None) -> None:
    """Open an interactive capture browser."""
    capture_paths = list(paths or [])
    workouts = load_workout_summaries(capture_paths)
    app_state = load_app_state(capture_paths)
    curses.wrapper(_run, workouts, app_state, _title(paths))


def app_summary_lines(state: dict[str, object]) -> list[str]:
    device = _dict(state.get("device"))
    watch_faces = _dict(state.get("watch_faces"))
    settings = _dict(state.get("settings"))
    alarms = _dict(state.get("alarms"))
    workouts = state.get("workouts")
    workout_count = len(workouts) if isinstance(workouts, list) else 0

    lines = [
        "App State",
        "",
        "Device",
        f"Name         : {_value(device.get('name'))}",
        f"Address      : {_value(device.get('address'))}",
        f"Battery      : {_battery(device)}",
        "",
        "Watch Faces",
        f"Display      : {_value(watch_faces.get('display_slot'))}",
        f"Slots        : {_slot_summary(watch_faces.get('slots'))}",
        f"Support      : {_support_summary(watch_faces.get('support'))}",
        "",
        "Captured Data",
        f"Settings     : {_count_mapping_values(settings)} value(s)",
        f"Alarms       : {_alarm_summary(alarms)}",
        f"Workouts     : {workout_count}",
    ]
    return lines


def workout_table_rows(workouts: Sequence[WorkoutSummary]) -> list[str]:
    rows = [
        "ID   Start               Time    Steps   Dist   Cal   HR       Done",
        "---  ------------------  ------  ------  -----  ----  -------  ----",
    ]
    for workout in workouts:
        rows.append(
            f"{workout.id:>3}  "
            f"{_short_time(workout.start or workout.listed_start):<18}  "
            f"{_duration(workout.valid_time):>6}  "
            f"{_value(workout.steps):>6}  "
            f"{_distance(workout.distance):>5}  "
            f"{_value(workout.calories):>4}  "
            f"{_heart_rate_summary(workout):>7}  "
            f"{'yes' if workout.heart_rate.complete else 'no':>4}"
        )
    return rows


def workout_detail_lines(workout: WorkoutSummary) -> list[str]:
    lines = [
        f"Workout {workout.id}",
        "",
        f"Listed start : {_value(workout.listed_start)}",
        f"Start        : {_value(workout.start)}",
        f"End          : {_value(workout.end)}",
        f"Valid time   : {_duration(workout.valid_time)} ({_value(workout.valid_time)}s)",
        f"Type         : {_value(workout.type)}",
        f"Steps        : {_value(workout.steps)}",
        f"Distance     : {_distance(workout.distance)} km ({_value(workout.distance)} m)",
        f"Calories     : {_value(workout.calories)}",
        "",
        "Series",
        f"Heart rate   : {_series_summary(workout.heart_rate)}",
        f"Steps        : {_series_summary(workout.steps_series)}",
        f"Distance     : {_series_summary(workout.distance_series)}",
        "",
        "Sources",
    ]
    sources = sorted(set(workout.sources))
    lines.extend(f"- {source}" for source in sources)
    if not sources:
        lines.append("- none")
    return lines


def _run(
    stdscr: curses.window,
    workouts: list[WorkoutSummary],
    app_state: dict[str, object],
    title: str,
) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    selected = 0
    scroll = 0
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        _draw_header(stdscr, width, title, len(workouts))
        if not workouts:
            _addstr(stdscr, 2, 0, "No workout captures found.", curses.A_BOLD)
            _draw_app_summary(stdscr, app_state, 4, 0, height, width)
        else:
            selected = max(0, min(selected, len(workouts) - 1))
            scroll = _draw_workouts(stdscr, workouts, selected, scroll, height, width)
            _draw_detail(stdscr, workouts[selected], app_state, height, width)
        _draw_footer(stdscr, height, width)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j"), ord("J")):
            selected = min(selected + 1, len(workouts) - 1)
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            selected = max(selected - 1, 0)
        elif key in (curses.KEY_NPAGE, ord(" ")):
            selected = min(selected + max(1, height - 8), len(workouts) - 1)
        elif key == curses.KEY_PPAGE:
            selected = max(selected - max(1, height - 8), 0)
        elif key in (ord("g"), ord("G")):
            selected = 0 if key == ord("g") else max(0, len(workouts) - 1)


def _draw_header(stdscr: curses.window, width: int, title: str, count: int) -> None:
    _addstr(stdscr, 0, 0, f"{title} - {count} workout(s)"[:width], curses.A_BOLD)


def _draw_footer(stdscr: curses.window, height: int, width: int) -> None:
    footer = "Up/Down or j/k move | PgUp/PgDn jump | g/G top/bottom | q quit"
    _addstr(stdscr, height - 1, 0, footer[:width], curses.A_DIM)


def _draw_workouts(
    stdscr: curses.window,
    workouts: Sequence[WorkoutSummary],
    selected: int,
    scroll: int,
    height: int,
    width: int,
) -> int:
    table_width = min(width, 78 if width < 120 else width // 2)
    rows = workout_table_rows(workouts)
    body_top = 2
    body_height = max(1, height - 4)
    first_data_line = 2
    visible_data_rows = max(1, body_height - first_data_line)
    if selected < scroll:
        scroll = selected
    elif selected >= scroll + visible_data_rows:
        scroll = selected - visible_data_rows + 1

    for index, row in enumerate(rows[:2]):
        _addstr(stdscr, body_top + index, 0, row[:table_width], curses.A_BOLD)
    for screen_index in range(visible_data_rows):
        workout_index = scroll + screen_index
        if workout_index >= len(workouts):
            break
        row = rows[workout_index + 2]
        attr = curses.A_REVERSE if workout_index == selected else curses.A_NORMAL
        _addstr(stdscr, body_top + first_data_line + screen_index, 0, row[:table_width], attr)
    return scroll


def _draw_detail(
    stdscr: curses.window,
    workout: WorkoutSummary,
    app_state: dict[str, object],
    height: int,
    width: int,
) -> None:
    if width < 120:
        return
    left = width // 2 + 2
    detail_width = max(20, width - left)
    lines = app_summary_lines(app_state) + ["", "Selected Workout", ""] + workout_detail_lines(workout)
    for index, line in enumerate(_wrapped_lines(lines, detail_width)):
        y = 2 + index
        if y >= height - 1:
            break
        headings = {"App State", "Device", "Watch Faces", "Captured Data", "Selected Workout"}
        attr = curses.A_BOLD if line in headings else curses.A_NORMAL
        _addstr(stdscr, y, left, line[:detail_width], attr)


def _draw_app_summary(
    stdscr: curses.window,
    app_state: dict[str, object],
    top: int,
    left: int,
    height: int,
    width: int,
) -> None:
    lines = _wrapped_lines(app_summary_lines(app_state), max(20, width - left))
    for index, line in enumerate(lines):
        y = top + index
        if y >= height - 1:
            break
        headings = {"App State", "Device", "Watch Faces", "Captured Data"}
        attr = curses.A_BOLD if line in headings else curses.A_NORMAL
        _addstr(stdscr, y, left, line[: max(0, width - left)], attr)


def _wrapped_lines(raw_lines: Sequence[str], width: int) -> list[str]:
    lines: list[str] = []
    for line in raw_lines:
        if not line:
            lines.append("")
            continue
        wrapped = textwrap.wrap(line, width=width, subsequent_indent="  ")
        lines.extend(wrapped or [""])
    return lines


def _title(paths: Sequence[str | Path] | None) -> str:
    if not paths:
        return "dafit-open captures"
    return "dafit-open captures: " + ", ".join(str(path) for path in paths)


def _short_time(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ").replace("+00:00", "")[:16]


def _duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minute:02d}m"
    if minute:
        return f"{minute}m{sec:02d}s"
    return f"{sec}s"


def _distance(meters: int | None) -> str:
    if meters is None:
        return "-"
    return f"{meters / 1000:.2f}"


def _value(value: object | None) -> str:
    return "-" if value is None else str(value)


def _heart_rate_summary(workout: WorkoutSummary) -> str:
    if not workout.heart_rate.values:
        return "-"
    return f"{workout.heart_rate.nonzero_count}/{len(workout.heart_rate.trimmed_values)}"


def _series_summary(series: object) -> str:
    values = getattr(series, "values")
    if not values:
        return "no samples"
    trimmed = getattr(series, "trimmed_values")
    return (
        f"{len(trimmed)} trimmed, {getattr(series, 'nonzero_count')} nonzero, "
        f"{getattr(series, 'chunks')} chunk(s), complete={getattr(series, 'complete')}"
    )


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _battery(device: dict[str, object]) -> str:
    fields = _dict(device.get("fields"))
    battery = fields.get("battery_level")
    if battery is None:
        return "-"
    return f"{battery}%"


def _slot_summary(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    counts: dict[str, int] = {}
    for slot in value:
        if not isinstance(slot, dict):
            continue
        slot_type = str(slot.get("kind") or slot.get("type") or "?")
        counts[slot_type] = counts.get(slot_type, 0) + 1
    by_type = ", ".join(f"{key}:{counts[key]}" for key in sorted(counts))
    return f"{len(value)} ({by_type})" if by_type else str(len(value))


def _support_summary(value: object) -> str:
    support = _dict(value)
    supported = support.get("supported")
    display = support.get("display_index")
    if not isinstance(supported, list):
        return "-"
    return f"display={_value(display)}, supported={','.join(str(item) for item in supported)}"


def _count_mapping_values(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    return sum(1 for key, item in value.items() if key != "sources" and item is not None)


def _alarm_summary(value: object) -> str:
    alarms = _dict(value)
    legacy = alarms.get("legacy_alarms")
    new = alarms.get("new_alarms")
    legacy_records = legacy if isinstance(legacy, list) else []
    new_records = new if isinstance(new, list) else []
    enabled = sum(
        1
        for item in legacy_records + new_records
        if isinstance(item, dict) and item.get("enabled")
    )
    return f"{len(legacy_records)} legacy, {len(new_records)} new, {enabled} enabled"


def _addstr(stdscr: curses.window, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    try:
        stdscr.addstr(y, x, text[: max(0, width - x - 1)], attr)
    except curses.error:
        pass

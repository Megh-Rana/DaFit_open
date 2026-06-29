"""Import Da Fit app log BLE traces into clean-room captures."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from .protocol import Frame, hex_bytes, parse_frame


HEX_BYTE_RE = re.compile(r"\b[0-9a-fA-F]{2}\b")
MESSAGE_TYPE_RE = re.compile(r"message type:\s*(-?\d+)", re.IGNORECASE)
DATA_RE = re.compile(
    r"(message content|onCharacteristicWrite|onCharacteristicChanged|onCharacteristicRead):\s*(.*)$",
    re.IGNORECASE,
)
CMD_RE = re.compile(r"\bcmd:\s*(-?\d+)", re.IGNORECASE)
TRANS_OFFSET_RE = re.compile(r"\btrans offset:\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class AppLogEvent:
    line: int
    timestamp: str | None
    kind: str
    data: bytes | None = None
    message_type: int | None = None
    command: int | None = None
    trans_offset: int | None = None
    frame: Frame | None = None

    def to_dict(self, include_data: bool = True) -> dict[str, Any]:
        item: dict[str, Any] = {
            "line": self.line,
            "timestamp": self.timestamp,
            "kind": self.kind,
        }
        if self.message_type is not None:
            item["message_type"] = self.message_type
        if self.command is not None:
            item["command"] = self.command
        if self.trans_offset is not None:
            item["trans_offset"] = self.trans_offset
        if self.data is not None:
            item["data_len"] = len(self.data)
            if include_data:
                item["data_hex"] = hex_bytes(self.data)
        if self.frame is not None:
            item["frame"] = {
                "flags": self.frame.flags,
                "packet_len": self.frame.packet_len,
                "command": self.frame.command,
                "payload_len": len(self.frame.payload),
                "payload_hex": hex_bytes(self.frame.payload) if include_data else None,
            }
        return item


def import_app_logs(paths: Iterable[str | Path], include_data: bool = True) -> dict[str, Any]:
    events: list[AppLogEvent] = []
    files = _expand_paths(paths)
    for path in files:
        events.extend(_parse_file(path))

    chunks = [event for event in events if event.kind == "tx_message" and event.message_type == 2 and event.data]
    transfer_payload = b"".join(event.data or b"" for event in chunks)
    ack_offsets = [event.trans_offset for event in events if event.trans_offset is not None]
    frames = [event for event in events if event.frame is not None]
    commands = _command_counts(frames)

    return {
        "schema": "dafit-open.app-log-import.v1",
        "sources": [str(path) for path in files],
        "summary": {
            "events": len(events),
            "frames": len(frames),
            "transfer_chunks": len(chunks),
            "transfer_payload_size": len(transfer_payload),
            "transfer_payload_sha256": hashlib.sha256(transfer_payload).hexdigest()
            if transfer_payload
            else None,
            "transfer_first_line": chunks[0].line if chunks else None,
            "transfer_last_line": chunks[-1].line if chunks else None,
            "ack_offsets": ack_offsets,
            "commands": commands,
        },
        "events": [event.to_dict(include_data=include_data) for event in events],
    }


def write_imported_app_log(
    capture: dict[str, Any],
    output: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> None:
    if out_dir:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        payload = _payload_from_capture(capture)
        if payload:
            (out_path / "transfer-payload.bin").write_bytes(payload)
    text = json.dumps(capture, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(text)
    else:
        print(text, end="")


def _expand_paths(paths: Iterable[str | Path]) -> list[Path]:
    expanded: list[Path] = []
    for path_value in paths:
        path = Path(path_value)
        if path.is_dir():
            expanded.extend(sorted(child for child in path.rglob("*") if child.is_file()))
        else:
            expanded.append(path)
    return expanded


def _parse_file(path: Path) -> list[AppLogEvent]:
    events: list[AppLogEvent] = []
    message_type: int | None = None
    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        timestamp = _timestamp(line)
        type_match = MESSAGE_TYPE_RE.search(line)
        if type_match:
            message_type = int(type_match.group(1))

        data_match = DATA_RE.search(line)
        if data_match:
            data = _parse_hex_bytes(data_match.group(2))
            if not data:
                continue
            label = data_match.group(1).lower()
            frame = parse_frame(data)
            if label == "message content":
                events.append(
                    AppLogEvent(
                        line=line_number,
                        timestamp=timestamp,
                        kind="tx_message",
                        data=data,
                        message_type=message_type,
                        command=frame.command if frame else None,
                        frame=frame,
                    )
                )
            elif label == "oncharacteristicchanged":
                events.append(
                    AppLogEvent(
                        line=line_number,
                        timestamp=timestamp,
                        kind="rx_notify",
                        data=data,
                        command=frame.command if frame else None,
                        frame=frame,
                    )
                )
            elif label == "oncharacteristicread":
                events.append(
                    AppLogEvent(
                        line=line_number,
                        timestamp=timestamp,
                        kind="rx_read",
                        data=data,
                        command=frame.command if frame else None,
                        frame=frame,
                    )
                )
            else:
                events.append(
                    AppLogEvent(
                        line=line_number,
                        timestamp=timestamp,
                        kind="tx_write_echo",
                        data=data,
                        message_type=message_type,
                        command=frame.command if frame else None,
                        frame=frame,
                    )
                )
            continue

        cmd_match = CMD_RE.search(line)
        if cmd_match:
            command = int(cmd_match.group(1)) & 0xFF
            events.append(
                AppLogEvent(
                    line=line_number,
                    timestamp=timestamp,
                    kind="parsed_command",
                    command=command,
                )
            )
            continue

        offset_match = TRANS_OFFSET_RE.search(line)
        if offset_match:
            events.append(
                AppLogEvent(
                    line=line_number,
                    timestamp=timestamp,
                    kind="transfer_offset",
                    trans_offset=int(offset_match.group(1)),
                )
            )
    return events


def _parse_hex_bytes(text: str) -> bytes:
    tokens = HEX_BYTE_RE.findall(text)
    if not tokens:
        return b""
    return bytes(int(token, 16) for token in tokens)


def _timestamp(line: str) -> str | None:
    match = re.match(r"(\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d{3})", line)
    return match.group(1) if match else None


def _command_counts(events: Iterable[AppLogEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.frame is None:
            continue
        key = f"0x{event.frame.command:02X}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _payload_from_capture(capture: dict[str, Any]) -> bytes:
    payload = bytearray()
    for event in capture.get("events", []):
        if event.get("kind") != "tx_message" or event.get("message_type") != 2:
            continue
        hex_text = event.get("data_hex")
        if isinstance(hex_text, str):
            payload.extend(_parse_hex_bytes(hex_text))
    return bytes(payload)

"""Helpers for Da Fit store watch-face `.bin` transfer files."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .protocol import (
    Packet,
    hex_bytes,
    store_watch_face_check_packet,
    store_watch_face_prepare_packet,
)
from .watchface_image import crp_crc16


DEFAULT_STORE_PACKET_LENGTH = 244


@dataclass(frozen=True)
class StoreWatchFacePlan:
    path: str
    size: int
    sha256: str
    crc16: int
    packet_length: int
    chunk_count: int
    prepare_packet: Packet
    success_packet: Packet
    chunks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "dafit-store-bin",
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "crc16": f"0x{self.crc16:04X}",
            "packet_length": self.packet_length,
            "chunk_count": self.chunk_count,
            "packets": {
                "prepare": _packet_dict(self.prepare_packet),
                "success": _packet_dict(self.success_packet),
                "chunks": self.chunks,
            },
        }


def inspect_store_watch_face_bin(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    data = file_path.read_bytes()
    return {
        "schema": "dafit-open.store-watch-face-bin.v1",
        "path": str(file_path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "crc16": f"0x{crp_crc16(data):04X}",
        "default_packet_length": DEFAULT_STORE_PACKET_LENGTH,
        "default_chunk_count": chunk_count(len(data), DEFAULT_STORE_PACKET_LENGTH),
        "first_bytes_hex": hex_bytes(data[:64]),
    }


def analyze_store_watch_face_bin(
    path: str | Path,
    scan_limit: int = 4096,
) -> dict[str, Any]:
    file_path = Path(path)
    data = file_path.read_bytes()
    interesting_values = {
        "watch_face_id_19719": 19719,
        "screen_width_466": 466,
        "screen_height_466": 466,
        "thumb_width_280": 280,
        "thumb_height_280": 280,
        "file_size": len(data),
    }
    return {
        "schema": "dafit-open.store-watch-face-bin-analysis.v1",
        "path": str(file_path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "crc16": f"0x{crp_crc16(data):04X}",
        "first_bytes_hex": hex_bytes(data[:128]),
        "value_hits": _find_value_hits(data, interesting_values),
        "zero_runs": _find_zero_runs(data, minimum=32, limit=12),
        "monotonic_u32_runs": _find_monotonic_u32_runs(data, scan_limit=scan_limit),
        "entropy_windows": _entropy_windows(data),
        "notes": [
            "Store watch-face bins are not the same format as custom ORIGINAL background payloads.",
            "Monotonic u32 runs are candidate offset/pointer tables, not confirmed field names.",
        ],
    }


def plan_store_watch_face_transfer(
    path: str | Path,
    packet_length: int = DEFAULT_STORE_PACKET_LENGTH,
    chunk_preview_count: int = 2,
) -> StoreWatchFacePlan:
    if packet_length <= 0 or packet_length > 0xFFFF:
        raise ValueError(f"packet length out of range: {packet_length}")
    file_path = Path(path)
    data = file_path.read_bytes()
    chunks = []
    for index, offset in enumerate(range(0, len(data), packet_length)):
        if index >= chunk_preview_count:
            break
        chunk = data[offset : offset + packet_length]
        chunks.append(
            {
                "index": index,
                "offset": offset,
                "data_len": len(chunk),
                "crc16": f"0x{crp_crc16(chunk):04X}",
                "data_hex": hex_bytes(chunk),
            }
        )
    return StoreWatchFacePlan(
        path=str(file_path),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        crc16=crp_crc16(data),
        packet_length=packet_length,
        chunk_count=chunk_count(len(data), packet_length),
        prepare_packet=store_watch_face_prepare_packet(len(data)),
        success_packet=store_watch_face_check_packet(True),
        chunks=chunks,
    )


def write_store_watch_face_plan(
    plan: StoreWatchFacePlan,
    output: str | Path | None = None,
) -> None:
    text = json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
    else:
        print(text, end="")


def download_store_watch_face_bin(url: str, output: str | Path) -> dict[str, Any]:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response:
        data = response.read()
    destination.write_bytes(data)
    info = inspect_store_watch_face_bin(destination)
    info["source_url"] = url
    return info


def chunk_count(size: int, packet_length: int) -> int:
    if packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    return (size + packet_length - 1) // packet_length


def _find_value_hits(data: bytes, values: dict[str, int]) -> list[dict[str, Any]]:
    hits = []
    for label, value in values.items():
        sizes = [2, 3, 4] if value <= 0xFFFFFF else [4]
        for size in sizes:
            if value >= 1 << (size * 8):
                continue
            for byteorder in ("little", "big"):
                needle = value.to_bytes(size, byteorder=byteorder)
                start = 0
                while True:
                    offset = data.find(needle, start)
                    if offset < 0:
                        break
                    hits.append(
                        {
                            "label": label,
                            "value": value,
                            "offset": offset,
                            "size": size,
                            "byteorder": byteorder,
                            "hex": hex_bytes(needle),
                        }
                    )
                    start = offset + 1
    hits.sort(key=lambda item: (int(item["offset"]), str(item["label"]), int(item["size"])))
    return hits[:80]


def _find_zero_runs(data: bytes, minimum: int, limit: int) -> list[dict[str, int]]:
    runs = []
    start = None
    for offset, value in enumerate(data + b"\x01"):
        if value == 0:
            if start is None:
                start = offset
            continue
        if start is not None:
            length = offset - start
            if length >= minimum:
                runs.append({"offset": start, "length": length})
                if len(runs) >= limit:
                    break
            start = None
    return runs


def _find_monotonic_u32_runs(data: bytes, scan_limit: int) -> list[dict[str, Any]]:
    runs = []
    end = min(len(data) - 16, scan_limit)
    for byteorder in ("little", "big"):
        for start in range(0, max(0, end), 4):
            values = []
            offset = start
            previous = None
            while offset + 4 <= len(data):
                value = int.from_bytes(data[offset : offset + 4], byteorder=byteorder)
                if value >= len(data) or (previous is not None and value <= previous):
                    break
                values.append(value)
                previous = value
                offset += 4
            if len(values) >= 8:
                runs.append(
                    {
                        "offset": start,
                        "byteorder": byteorder,
                        "count": len(values),
                        "first_values": values[:6],
                        "last_values": values[-6:],
                    }
                )
    runs.sort(key=lambda item: (-int(item["count"]), int(item["offset"])))
    return runs[:12]


def _entropy_windows(data: bytes, window: int = 4096) -> list[dict[str, Any]]:
    windows = []
    for offset in range(0, len(data), window):
        chunk = data[offset : offset + window]
        if not chunk:
            continue
        counts = [0] * 256
        for value in chunk:
            counts[value] += 1
        entropy = -sum(
            (count / len(chunk)) * math.log2(count / len(chunk))
            for count in counts
            if count
        )
        windows.append(
            {
                "offset": offset,
                "length": len(chunk),
                "entropy": round(entropy, 4),
                "first_bytes_hex": hex_bytes(chunk[:8]),
            }
        )
    return windows


def _packet_dict(packet: Packet) -> dict[str, Any]:
    return {
        "command": packet.command,
        "payload_hex": hex_bytes(packet.payload),
        "frame_hex": hex_bytes(packet.build()),
    }

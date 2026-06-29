"""Helpers for Da Fit store watch-face `.bin` transfer files."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
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


def _packet_dict(packet: Packet) -> dict[str, Any]:
    return {
        "command": packet.command,
        "payload_hex": hex_bytes(packet.payload),
        "frame_hex": hex_bytes(packet.build()),
    }

"""Clean-room image preparation for experimental watch-face uploads."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .protocol import (
    Packet,
    file_transfer_start_packet,
    hex_bytes,
    watch_face_transfer_prepare_packet,
)


@dataclass(frozen=True)
class PixelImage:
    width: int
    height: int
    pixels: list[tuple[int, int, int]]

    def resized_cover(self, width: int, height: int) -> "PixelImage":
        if width <= 0 or height <= 0:
            raise ValueError("target image size must be positive")
        source_ratio = self.width / self.height
        target_ratio = width / height
        if source_ratio > target_ratio:
            crop_height = self.height
            crop_width = max(1, round(self.height * target_ratio))
        else:
            crop_width = self.width
            crop_height = max(1, round(self.width / target_ratio))
        crop_x = (self.width - crop_width) // 2
        crop_y = (self.height - crop_height) // 2

        output: list[tuple[int, int, int]] = []
        for y in range(height):
            source_y = crop_y + min(crop_height - 1, (y * crop_height) // height)
            row_offset = source_y * self.width
            for x in range(width):
                source_x = crop_x + min(crop_width - 1, (x * crop_width) // width)
                output.append(self.pixels[row_offset + source_x])
        return PixelImage(width=width, height=height, pixels=output)

    def to_rgb565(self, byteorder: str = "little") -> bytes:
        if byteorder not in {"little", "big"}:
            raise ValueError("rgb565 byteorder must be 'little' or 'big'")
        data = bytearray()
        for red, green, blue in self.pixels:
            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            data.extend(value.to_bytes(2, byteorder))
        return bytes(data)

    def to_ppm(self) -> bytes:
        header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
        body = bytearray()
        for red, green, blue in self.pixels:
            body.extend((red, green, blue))
        return header + bytes(body)


@dataclass(frozen=True)
class WatchFacePlan:
    width: int
    height: int
    thumb_width: int
    thumb_height: int
    files: list[dict[str, Any]]
    prepare_packet: Packet
    start_packets: list[tuple[str, Packet]]
    chunks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "raw-rgb565",
            "width": self.width,
            "height": self.height,
            "thumb_width": self.thumb_width,
            "thumb_height": self.thumb_height,
            "files": self.files,
            "packets": {
                "prepare": _packet_dict(self.prepare_packet),
                "start": [
                    {"file": filename, **_packet_dict(packet)}
                    for filename, packet in self.start_packets
                ],
                "chunks": self.chunks,
            },
        }


def build_watch_face_package(
    image_path: str | Path,
    out_dir: str | Path,
    width: int = 240,
    height: int = 240,
    thumb_width: int = 80,
    thumb_height: int = 80,
    byteorder: str = "little",
) -> dict[str, Any]:
    source = load_image(image_path)
    face = source.resized_cover(width, height)
    thumb = source.resized_cover(thumb_width, thumb_height)

    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    face_path = output / "face.rgb565"
    thumb_path = output / "thumb.rgb565"
    preview_path = output / "preview.ppm"
    face_path.write_bytes(face.to_rgb565(byteorder))
    thumb_path.write_bytes(thumb.to_rgb565(byteorder))
    preview_path.write_bytes(face.to_ppm())

    manifest = {
        "schema": "dafit-open.watch-face-package.v1",
        "source": str(image_path),
        "format": "raw-rgb565",
        "byteorder": byteorder,
        "width": width,
        "height": height,
        "thumb_width": thumb_width,
        "thumb_height": thumb_height,
        "files": [
            _file_record(face_path, "face"),
            _file_record(thumb_path, "thumbnail"),
            _file_record(preview_path, "preview"),
        ],
        "notes": [
            "raw-rgb565 is an experimental local package format",
            "the Da Fit app normally compresses watch-face images before transfer",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_image(path: str | Path) -> PixelImage:
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    if suffix in {".ppm", ".pnm"}:
        return _load_ppm(image_path)
    try:
        from PIL import Image  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PNG/JPEG input requires Pillow. Install it with `pip install Pillow`, "
            "or use a PPM image for dependency-free testing."
        ) from exc
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        pixels = [(red, green, blue) for red, green, blue in rgb.getdata()]
        return PixelImage(width=rgb.width, height=rgb.height, pixels=pixels)


def load_package_manifest(package_dir: str | Path) -> dict[str, Any]:
    manifest_path = Path(package_dir) / "manifest.json"
    return json.loads(manifest_path.read_text())


def inspect_watch_face_package(package_dir: str | Path) -> dict[str, Any]:
    package_path = Path(package_dir)
    manifest = load_package_manifest(package_path)
    files = []
    valid = True
    transferable_size = 0
    transferable_files = 0
    for file_info in manifest.get("files", []):
        path = package_path / str(file_info.get("path", ""))
        record = dict(file_info)
        record["exists"] = path.exists()
        if path.exists():
            data = path.read_bytes()
            actual_size = len(data)
            actual_sha = hashlib.sha256(data).hexdigest()
            record["actual_size"] = actual_size
            record["actual_sha256"] = actual_sha
            record["size_ok"] = actual_size == int(file_info.get("size", -1))
            record["sha256_ok"] = actual_sha == file_info.get("sha256")
            record["crc16"] = f"0x{crp_crc16(data):04X}"
            if file_info.get("role") in {"face", "thumbnail"}:
                transferable_files += 1
                transferable_size += actual_size
        else:
            record["actual_size"] = None
            record["actual_sha256"] = None
            record["size_ok"] = False
            record["sha256_ok"] = False
            record["crc16"] = None
        valid = valid and bool(record["exists"] and record["size_ok"] and record["sha256_ok"])
        files.append(record)
    valid = valid and bool(files)
    return {
        "schema": "dafit-open.watch-face-package-inspection.v1",
        "package_dir": str(package_path),
        "valid": valid,
        "format": manifest.get("format"),
        "byteorder": manifest.get("byteorder"),
        "width": manifest.get("width"),
        "height": manifest.get("height"),
        "thumb_width": manifest.get("thumb_width"),
        "thumb_height": manifest.get("thumb_height"),
        "transferable_files": transferable_files,
        "transferable_size": transferable_size,
        "files": files,
    }


def plan_watch_face_transfer(
    package_dir: str | Path,
    transfer_type: int = 14,
    include_thumbnail: bool = True,
    packet_length: int | None = None,
    chunk_preview_count: int = 1,
    name_mode: str = "path",
) -> WatchFacePlan:
    if name_mode not in {"path", "role"}:
        raise ValueError("name mode must be 'path' or 'role'")
    package_path = Path(package_dir)
    manifest = load_package_manifest(package_path)
    files = [
        file_info
        for file_info in manifest.get("files", [])
        if file_info.get("role") == "face" or (include_thumbnail and file_info.get("role") == "thumbnail")
    ]
    if not files:
        raise ValueError(f"no transferable files found in {package_path}")
    total_size = sum(int(file_info["size"]) for file_info in files)
    prepare_packet = watch_face_transfer_prepare_packet(total_size, len(files))
    start_packets = []
    chunks = []
    for file_info in files:
        filename = str(file_info["path"])
        transfer_name = _transfer_name(file_info, filename, name_mode)
        file_info["transfer_name"] = transfer_name
        file_path = package_path / filename
        file_data = file_path.read_bytes()
        file_info["crc16"] = f"0x{crp_crc16(file_data):04X}"
        start_packets.append(
            (
                filename,
                file_transfer_start_packet(
                    transfer_type,
                    int(file_info["size"]),
                    transfer_name,
                ),
            )
        )
        if packet_length is not None:
            file_info["packet_length"] = packet_length
            file_info["chunk_count"] = _chunk_count(len(file_data), packet_length)
            for offset in _chunk_offsets(len(file_data), packet_length, chunk_preview_count):
                chunk_data = file_data[offset : offset + packet_length]
                chunks.append(
                    {
                        "file": filename,
                        "offset": offset,
                        "data_len": len(chunk_data),
                        "crc16": f"0x{crp_crc16(chunk_data):04X}",
                        "frame_hex": hex_bytes(wrap_transfer_chunk(chunk_data, packet_length)),
                    }
                )
    return WatchFacePlan(
        width=int(manifest["width"]),
        height=int(manifest["height"]),
        thumb_width=int(manifest["thumb_width"]),
        thumb_height=int(manifest["thumb_height"]),
        files=files,
        prepare_packet=prepare_packet,
        start_packets=start_packets,
        chunks=chunks,
    )


def write_transfer_plan(plan: WatchFacePlan, output: str | Path | None = None) -> None:
    text = json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
    else:
        print(text, end="")


def crp_crc16(data: bytes, initial: int = 0xFEEA) -> int:
    value = initial
    for byte in data:
        swapped = (((value & 0x00FF) << 8) | ((value & 0xFF00) >> 8)) ^ byte
        mixed = swapped ^ ((swapped & 0x00FF) >> 4)
        mixed ^= (((mixed & 0x00FF) << 8) << 4)
        value = (mixed ^ (((mixed & 0x00FF) << 4) << 1)) & 0xFFFF
    return value


def wrap_transfer_chunk(data: bytes, packet_length: int) -> bytes:
    if packet_length <= 0 or packet_length > 0xFFFF:
        raise ValueError(f"packet length out of range: {packet_length}")
    if len(data) > packet_length:
        raise ValueError("chunk data is larger than packet length")
    crc = crp_crc16(data).to_bytes(2, "big")
    if packet_length == 64:
        return bytes([0xFF, 0xFF]) + crc + bytes([len(data) & 0xFF]) + data
    return bytes([0xFE]) + crc + bytes([len(data) & 0xFF]) + data


def _chunk_offsets(file_size: int, packet_length: int, preview_count: int) -> list[int]:
    if packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    if preview_count <= 0:
        return []
    offsets = []
    for index in range(preview_count):
        offset = index * packet_length
        if offset >= file_size:
            break
        offsets.append(offset)
    return offsets


def _chunk_count(file_size: int, packet_length: int) -> int:
    if packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    return (file_size + packet_length - 1) // packet_length


def _packet_dict(packet: Packet) -> dict[str, Any]:
    return {
        "command": packet.command,
        "payload_hex": hex_bytes(packet.payload),
        "frame_hex": hex_bytes(packet.build()),
    }


def _file_record(path: Path, role: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "role": role,
        "path": path.name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _transfer_name(file_info: dict[str, Any], filename: str, name_mode: str) -> str:
    if name_mode == "role":
        role = str(file_info.get("role") or Path(filename).stem or "file")
        if role == "thumbnail":
            role = "thumb"
        return f"{role[:5]}.bin"
    return Path(filename).name


def _load_ppm(path: Path) -> PixelImage:
    data = path.read_bytes()
    tokens, body_offset = _ppm_header_tokens(data, 4)
    magic = tokens[0]
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if max_value <= 0 or max_value > 255:
        raise ValueError("only 8-bit PPM files are supported")
    if magic == "P6":
        expected = width * height * 3
        body = data[body_offset : body_offset + expected]
        if len(body) != expected:
            raise ValueError("truncated PPM image data")
        pixels = [
            (body[index], body[index + 1], body[index + 2])
            for index in range(0, len(body), 3)
        ]
        return PixelImage(width=width, height=height, pixels=pixels)
    if magic == "P3":
        text = data[body_offset:].decode("ascii", errors="strict")
        values = [int(value) for value in text.split()]
        if len(values) < width * height * 3:
            raise ValueError("truncated PPM image data")
        pixels = [
            (values[index], values[index + 1], values[index + 2])
            for index in range(0, width * height * 3, 3)
        ]
        return PixelImage(width=width, height=height, pixels=pixels)
    raise ValueError(f"unsupported PPM magic: {magic}")


def _ppm_header_tokens(data: bytes, count: int) -> tuple[list[str], int]:
    tokens: list[str] = []
    index = 0
    while len(tokens) < count:
        while index < len(data) and chr(data[index]).isspace():
            index += 1
        if index >= len(data):
            raise ValueError("truncated PPM header")
        if data[index] == ord("#"):
            while index < len(data) and data[index] not in b"\r\n":
                index += 1
            continue
        start = index
        while index < len(data) and not chr(data[index]).isspace():
            index += 1
        tokens.append(data[start:index].decode("ascii"))
    while index < len(data) and chr(data[index]).isspace():
        index += 1
    return tokens, index

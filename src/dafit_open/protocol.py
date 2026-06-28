"""Packet framing and GATT constants inferred from observed app behavior."""

from __future__ import annotations

from dataclasses import dataclass


BLUETOOTH_BASE_SUFFIX = "-0000-1000-8000-00805f9b34fb"


def short_uuid(value: str) -> str:
    """Expand a 16-bit BLE UUID to the canonical 128-bit form."""
    return f"0000{value.lower()}{BLUETOOTH_BASE_SUFFIX}"


CLIENT_CHARACTERISTIC_CONFIG = short_uuid("2902")

CRP_SERVICE = short_uuid("feea")
CRP_NOTIFY_PRIMARY = short_uuid("fee1")
CRP_WRITE_PRIMARY = short_uuid("fee2")
CRP_NOTIFY_SECONDARY = short_uuid("fee3")
CRP_FEE4 = short_uuid("fee4")
CRP_WRITE_CMD_1 = short_uuid("fee5")
CRP_WRITE_CMD_2 = short_uuid("fee6")
CRP_NOTIFY_EXT_1 = short_uuid("fee7")
CRP_NOTIFY_EXT_2 = short_uuid("fee8")
CRP_HISILICON = short_uuid("fee9")

BATTERY_SERVICE = short_uuid("180f")
BATTERY_LEVEL = short_uuid("2a19")
DEVICE_INFO_SERVICE = short_uuid("180a")
FIRMWARE_REVISION = short_uuid("2a28")
MANUFACTURER_NAME = short_uuid("2a29")
MODEL_NUMBER = short_uuid("2a24")
HEART_RATE_SERVICE = short_uuid("180d")
HEART_RATE_MEASUREMENT = short_uuid("2a37")

ALT_SERVICE_3802 = short_uuid("3802")
ALT_CHARACTERISTIC_4A02 = short_uuid("4a02")


HEADER = bytes([0xFE, 0xEA])


@dataclass(frozen=True)
class Packet:
    command: int
    payload: bytes = b""
    mtu_payload: int = 20

    def build(self) -> bytes:
        return build_packet(self.command, self.payload, self.mtu_payload)


@dataclass(frozen=True)
class Frame:
    flags: int
    packet_len: int
    command: int
    payload: bytes


@dataclass(frozen=True)
class WatchFaceSlot:
    index: int
    kind: str
    watch_face_id: int


def build_packet(command: int, payload: bytes = b"", mtu_payload: int = 20) -> bytes:
    """Build the common CRP command frame.

    Frame shape:
        FE EA flags length command payload...

    For default 20-byte BLE payload mode, observed packets use flag 0x10.
    For larger MTU mode, observed packets use 0x20 plus the high length byte.
    """
    payload = bytes(payload)
    packet_len = len(payload) + 5
    if packet_len > 0x0FFF:
        raise ValueError(f"packet too large: {packet_len}")

    if mtu_payload == 20:
        flags = 0x10
    elif packet_len > 0xFF:
        flags = 0x20 + (packet_len >> 8)
    else:
        flags = 0x20

    return bytes(
        [
            HEADER[0],
            HEADER[1],
            flags & 0xFF,
            packet_len & 0xFF,
            command & 0xFF,
        ]
    ) + payload


def parse_frame_prefix(data: bytes) -> tuple[int, int, int] | None:
    """Return `(flags, packet_len, command)` when data looks like a CRP frame."""
    data = bytes(data)
    if len(data) < 5 or data[:2] != HEADER:
        return None
    flags = data[2]
    packet_len = data[3]
    if flags >= 0x20:
        packet_len |= (flags - 0x20) << 8
    return flags, packet_len, data[4]


def parse_frame(data: bytes) -> Frame | None:
    parsed = parse_frame_prefix(data)
    if parsed is None:
        return None
    flags, packet_len, command = parsed
    return Frame(flags=flags, packet_len=packet_len, command=command, payload=bytes(data[5:]))


def decode_frame(frame: Frame) -> str | None:
    if frame.command == 0x2E and frame.payload:
        return f"device_version={frame.payload[0]}"
    if frame.command == 0x29 and frame.payload:
        return f"display_watch_face={frame.payload[0]}"
    if frame.command == 0xA6:
        slots = decode_watch_face_list(frame.payload)
        if slots is None:
            return None
        return "watch_faces=[" + ", ".join(
            f"index={slot.index} type={slot.kind} id={slot.watch_face_id}"
            for slot in slots
        ) + "]"
    if frame.command == 0xB4:
        return decode_watch_face_subcommand(frame.payload)
    return None


def decode_watch_face_subcommand(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    subcommand = payload[0]
    data = payload[1:]
    if subcommand == 20 and len(data) >= 12:
        values = [
            data[0] + (data[1] << 8),
            data[2] + (data[3] << 8),
            data[4] + (data[5] << 8),
            data[6] + (data[7] << 8),
            data[8] + (data[9] << 8),
            data[10] + (data[11] << 8),
        ]
        return (
            "watch_face_screen="
            f"width={values[0]} height={values[1]} corner={values[2]} "
            f"thumb_width={values[3]} thumb_height={values[4]} thumb_corner={values[5]}"
        )
    if subcommand == 0 and len(data) >= 2:
        display_index = (data[0] << 8) + data[1]
        supported = list(data[2:])
        return f"support_watch_faces=display_index={display_index} supported={supported}"
    return f"watch_face_subcommand=0x{subcommand:02X} payload={hex_bytes(data)}"


def decode_watch_face_list(payload: bytes) -> list[WatchFaceSlot] | None:
    payload = bytes(payload)
    if len(payload) < 2 or payload[0] != 0x01:
        return None
    count = payload[1]
    slots: list[WatchFaceSlot] = []
    for offset in range(2, len(payload), 4):
        if offset + 4 > len(payload):
            break
        kind_byte = payload[offset + 1]
        kind = chr(kind_byte) if 32 <= kind_byte <= 126 else f"0x{kind_byte:02X}"
        watch_face_id = (payload[offset + 2] << 8) + payload[offset + 3]
        slots.append(
            WatchFaceSlot(
                index=payload[offset],
                kind=kind,
                watch_face_id=watch_face_id,
            )
        )
    if len(slots) != count:
        return slots
    return slots


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


QUERY_DEVICE_VERSION = Packet(0x2E)
QUERY_DISPLAY_WATCH_FACE = Packet(0x29)
QUERY_WATCH_FACE_LIST = Packet(0xA6, bytes([0x01]))
QUERY_WATCH_FACE_SCREEN = Packet(0xB4, bytes([0x14]))
QUERY_SUPPORT_WATCH_FACE = Packet(0x84)
QUERY_SUPPORT_WATCH_FACE_BASE = Packet(0xB4, bytes([0x00]))
QUERY_JIELI_DOWNLOAD_WATCH_FACE_LIST = Packet(0xB4, bytes([0x12]))
QUERY_JIELI_SUPPORT_WATCH_FACE = Packet(0xB4, bytes([0x10]))
QUERY_HISILICON_SUPPORT_WATCH_FACE = Packet(0xB4, bytes([0x20]))

DEFAULT_QUERY_PACKETS = [
    QUERY_DEVICE_VERSION,
    QUERY_DISPLAY_WATCH_FACE,
    QUERY_WATCH_FACE_LIST,
]

WATCH_FACE_QUERY_PACKETS = [
    *DEFAULT_QUERY_PACKETS,
    QUERY_WATCH_FACE_SCREEN,
]

WATCH_FACE_SUPPORT_QUERY_PACKETS = [
    QUERY_SUPPORT_WATCH_FACE,
    QUERY_SUPPORT_WATCH_FACE_BASE,
    QUERY_JIELI_DOWNLOAD_WATCH_FACE_LIST,
    QUERY_JIELI_SUPPORT_WATCH_FACE,
    QUERY_HISILICON_SUPPORT_WATCH_FACE,
    QUERY_WATCH_FACE_SCREEN,
]

QUERY_SETS = {
    "default": DEFAULT_QUERY_PACKETS,
    "watchface": WATCH_FACE_QUERY_PACKETS,
    "watchface-support": WATCH_FACE_SUPPORT_QUERY_PACKETS,
}

"""Packet framing and GATT constants inferred from observed app behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


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
    if frame.command == 0x19 and frame.payload:
        return f"display_watch_face_set={frame.payload[0]}"
    if frame.command == 0x26:
        return decode_goal_step(frame.payload)
    if frame.command == 0x2E and frame.payload:
        return f"device_version={frame.payload[0]}"
    if frame.command == 0x33:
        return decode_history_step_sleep_marker(frame.payload)
    if frame.command == 0x37:
        return f"movement_heart_rate payload={hex_bytes(frame.payload)}"
    if frame.command == 0x3D:
        return f"last_24h_blood_pressure payload={hex_bytes(frame.payload)}"
    if frame.command == 0x3E:
        return f"last_24h_blood_oxygen payload={hex_bytes(frame.payload)}"
    if frame.command == 0x29 and frame.payload:
        return f"display_watch_face={frame.payload[0]}"
    if frame.command == 0xAB:
        return decode_history_dynamic(frame.payload)
    if frame.command == 0xB2:
        return decode_training_history(frame.payload)
    if frame.command == 0xB6:
        return decode_history_step_sleep_detail(frame.payload)
    if frame.command == 0xB7:
        return decode_file_transfer_frame(frame.payload)
    if frame.command == 0xB8:
        return decode_sleep_time(frame.payload)
    if frame.command == 0x84:
        return decode_support_watch_faces(frame.payload)
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


def decode_goal_step(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return "goal_step=<empty>"
    value = int.from_bytes(payload[:4], byteorder="little", signed=False)
    return f"goal_step={value} payload={hex_bytes(payload)}"


def decode_history_step_sleep_marker(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    marker = payload[0]
    if marker <= 2:
        return f"history_step day={marker} payload={hex_bytes(payload[1:])}"
    return f"history_sleep_marker marker={marker} payload={hex_bytes(payload[1:])}"


def decode_history_step_sleep_detail(payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) < 2:
        return None
    kind = payload[0]
    day = payload[1]
    labels = {0: "step", 1: "sleep", 2: "timing_heart_rate"}
    return f"history_{labels.get(kind, f'kind_{kind}')} day={day} payload={hex_bytes(payload[2:])}"


def decode_history_dynamic(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    labels = {0: "heart_rate", 1: "blood_pressure", 2: "blood_oxygen"}
    kind = payload[0]
    data = payload[1:]
    if kind == 0:
        records = _decode_counted_records(data, 5, _decode_heart_rate_record)
        if records is not None:
            return f"history_heart_rate records={records}"
    if kind == 1:
        records = _decode_counted_records(data, 6, _decode_blood_pressure_record)
        if records is not None:
            return f"history_blood_pressure records={records}"
    if kind == 2:
        records = _decode_counted_records(data, 5, _decode_blood_oxygen_record)
        if records is not None:
            return f"history_blood_oxygen records={records}"
    return f"history_{labels.get(kind, f'kind_{kind}')} payload={hex_bytes(data)}"


def decode_training_history(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    subcommands = {0: "history_training_detail", 6: "history_training_list"}
    label = subcommands.get(payload[0], "training_subcommand")
    timestamps = _find_plausible_timestamps(payload)
    if timestamps:
        return f"{label} timestamps={timestamps} payload={hex_bytes(payload)}"
    return f"{label} payload={hex_bytes(payload)}"


def decode_sleep_time(payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) >= 3 and payload[0] == 3:
        return f"sleep_time start_hour={payload[1]} end_hour={payload[2]}"
    return f"sleep_time payload={hex_bytes(payload)}"


def decode_file_transfer_frame(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    labels = {
        0: "file_transfer_start",
        3: "file_transfer_check_ok",
        4: "file_transfer_check_failed",
        5: "file_transfer_abort",
    }
    if payload[0] == 0 and len(payload) >= 6:
        transfer_type = payload[1]
        size = int.from_bytes(payload[2:6], byteorder="little", signed=False)
        name = payload[6:].decode("utf-8", errors="replace").rstrip("\x00")
        return f"file_transfer_start type={transfer_type} size={size} name={name!r}"
    return f"{labels.get(payload[0], 'file_transfer')} payload={hex_bytes(payload)}"


def _decode_counted_records(data: bytes, record_size: int, decoder) -> list[str] | None:
    if not data:
        return []
    count = data[0]
    records_data = data[1:]
    if len(records_data) != count * record_size:
        return None
    return [decoder(records_data[offset : offset + record_size]) for offset in range(0, len(records_data), record_size)]


def _decode_heart_rate_record(record: bytes) -> str:
    bpm = record[0]
    timestamp = int.from_bytes(record[1:5], "little")
    return f"bpm={bpm}@{_format_timestamp(timestamp)}"


def _decode_blood_pressure_record(record: bytes) -> str:
    systolic = record[0]
    diastolic = record[1]
    timestamp = int.from_bytes(record[2:6], "little")
    return f"{systolic}/{diastolic}@{_format_timestamp(timestamp)}"


def _decode_blood_oxygen_record(record: bytes) -> str:
    spo2 = record[0]
    timestamp = int.from_bytes(record[1:5], "little")
    return f"spo2={spo2}@{_format_timestamp(timestamp)}"


def _find_plausible_timestamps(data: bytes) -> list[str]:
    timestamps = []
    for offset in range(0, max(0, len(data) - 3)):
        value = int.from_bytes(data[offset : offset + 4], "little")
        if 1_577_836_800 <= value <= 2_051_222_400:
            timestamps.append(f"offset={offset}:{_format_timestamp(value)}")
    return timestamps


def _format_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def decode_support_watch_faces(payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) < 2:
        return None
    display_index = (payload[0] << 8) + payload[1]
    supported = list(payload[2:])
    return f"support_watch_faces=display_index={display_index} supported={supported}"


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
        return f"watch_face_subcommand=0x00 display_index={display_index} supported={supported}"
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


def set_display_watch_face_packet(index: int) -> Packet:
    if not 0 <= index <= 0xFF:
        raise ValueError(f"watch-face index must fit in one byte: {index}")
    return Packet(0x19, bytes([index]))


def watch_face_transfer_prepare_packet(total_size: int, file_count: int) -> Packet:
    if not 0 <= total_size <= 0xFFFFFFFF:
        raise ValueError(f"total size must fit in uint32: {total_size}")
    if not 0 <= file_count <= 0xFF:
        raise ValueError(f"file count must fit in one byte: {file_count}")
    return Packet(0xB4, bytes([0x01]) + total_size.to_bytes(4, "little") + bytes([file_count]))


def file_transfer_start_packet(transfer_type: int, size: int, name: str) -> Packet:
    if not 0 <= transfer_type <= 0xFF:
        raise ValueError(f"transfer type must fit in one byte: {transfer_type}")
    if not 0 <= size <= 0xFFFFFFFF:
        raise ValueError(f"size must fit in uint32: {size}")
    encoded_name = name.encode("utf-8")[:160]
    return Packet(0xB7, bytes([0x00, transfer_type]) + size.to_bytes(4, "little") + encoded_name)


SET_DISPLAY_WATCH_FACE_COMMAND = 0x19
QUERY_DEVICE_VERSION = Packet(0x2E)
QUERY_DISPLAY_WATCH_FACE = Packet(0x29)
QUERY_WATCH_FACE_LIST = Packet(0xA6, bytes([0x01]))
QUERY_WATCH_FACE_SCREEN = Packet(0xB4, bytes([0x14]))
QUERY_SUPPORT_WATCH_FACE = Packet(0x84)
QUERY_SUPPORT_WATCH_FACE_BASE = Packet(0xB4, bytes([0x00]))
QUERY_JIELI_DOWNLOAD_WATCH_FACE_LIST = Packet(0xB4, bytes([0x12]))
QUERY_JIELI_SUPPORT_WATCH_FACE = Packet(0xB4, bytes([0x10]))
QUERY_HISILICON_SUPPORT_WATCH_FACE = Packet(0xB4, bytes([0x20]))
QUERY_GOAL_STEP = Packet(0x26)
QUERY_SLEEP_TIME = Packet(0xB8, bytes([0x03]))
QUERY_HISTORY_STEP_TODAY = Packet(0x33, bytes([0x00]))
QUERY_HISTORY_STEP_DETAIL_TODAY = Packet(0xB6, bytes([0x00, 0x00]))
QUERY_HISTORY_HEART_RATE = Packet(0xAB, bytes([0x00]))
QUERY_HISTORY_BLOOD_PRESSURE = Packet(0xAB, bytes([0x01]))
QUERY_HISTORY_BLOOD_OXYGEN = Packet(0xAB, bytes([0x02]))
QUERY_LAST_24H_BLOOD_PRESSURE = Packet(0x3D, bytes([0x00]))
QUERY_LAST_24H_BLOOD_OXYGEN = Packet(0x3E, bytes([0x00]))
QUERY_MOVEMENT_HEART_RATE = Packet(0x37)
QUERY_HISTORY_TRAINING_LIST = Packet(0xB2, bytes([0x06]))
QUERY_HISTORY_TRAINING_DETAIL = Packet(0xB2, bytes([0x00]))

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

HEALTH_BASIC_QUERY_PACKETS = [
    QUERY_GOAL_STEP,
    QUERY_SLEEP_TIME,
    QUERY_HISTORY_STEP_TODAY,
    QUERY_HISTORY_STEP_DETAIL_TODAY,
    QUERY_HISTORY_HEART_RATE,
    QUERY_HISTORY_BLOOD_PRESSURE,
    QUERY_HISTORY_BLOOD_OXYGEN,
    QUERY_LAST_24H_BLOOD_PRESSURE,
    QUERY_LAST_24H_BLOOD_OXYGEN,
    QUERY_MOVEMENT_HEART_RATE,
    QUERY_HISTORY_TRAINING_LIST,
    QUERY_HISTORY_TRAINING_DETAIL,
]

HEALTH_HISTORY_QUERY_PACKETS = [
    QUERY_GOAL_STEP,
    QUERY_HISTORY_HEART_RATE,
    QUERY_HISTORY_BLOOD_PRESSURE,
    QUERY_HISTORY_BLOOD_OXYGEN,
    QUERY_HISTORY_TRAINING_DETAIL,
]

HEALTH_EXTENDED_QUERY_PACKETS = [
    QUERY_SLEEP_TIME,
    QUERY_HISTORY_STEP_TODAY,
    QUERY_HISTORY_STEP_DETAIL_TODAY,
    QUERY_LAST_24H_BLOOD_PRESSURE,
    QUERY_LAST_24H_BLOOD_OXYGEN,
    QUERY_MOVEMENT_HEART_RATE,
    QUERY_HISTORY_TRAINING_LIST,
]

QUERY_SETS = {
    "default": DEFAULT_QUERY_PACKETS,
    "health-basic": HEALTH_BASIC_QUERY_PACKETS,
    "health-extended": HEALTH_EXTENDED_QUERY_PACKETS,
    "health-history": HEALTH_HISTORY_QUERY_PACKETS,
    "watchface": WATCH_FACE_QUERY_PACKETS,
    "watchface-support": WATCH_FACE_SUPPORT_QUERY_PACKETS,
}

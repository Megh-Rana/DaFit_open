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
class AlarmInfo:
    id: int
    enabled: bool
    hour: int
    minute: int
    repeat_mode: int
    date: str | None = None
    raw_type: int | None = None

    def to_dict(self) -> dict[str, int | bool | str | None]:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "hour": self.hour,
            "minute": self.minute,
            "repeat_mode": self.repeat_mode,
            "date": self.date,
            "raw_type": self.raw_type,
        }


@dataclass(frozen=True)
class WatchFaceSlot:
    index: int
    kind: str
    watch_face_id: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "index": self.index,
            "kind": self.kind,
            "watch_face_id": self.watch_face_id,
        }


@dataclass(frozen=True)
class WatchFaceSupport:
    display_index: int
    supported: list[int]

    def to_dict(self) -> dict[str, int | list[int]]:
        return {
            "display_index": self.display_index,
            "supported": self.supported,
        }


@dataclass(frozen=True)
class WatchFaceScreen:
    width: int
    height: int
    corner: int
    thumb_width: int
    thumb_height: int
    thumb_corner: int

    def to_dict(self) -> dict[str, int]:
        return {
            "width": self.width,
            "height": self.height,
            "corner": self.corner,
            "thumb_width": self.thumb_width,
            "thumb_height": self.thumb_height,
            "thumb_corner": self.thumb_corner,
        }


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
    if frame.command == 0x21:
        return decode_alarm_list(frame.payload)
    if frame.command == 0x18 and frame.payload:
        return f"display_time_enabled={frame.payload[0] == 1} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x26:
        return decode_goal_step(frame.payload)
    if frame.command == 0x27 and frame.payload:
        return f"time_system={frame.payload[0]} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x28 and frame.payload:
        enabled = frame.payload[0] == 1
        return f"quick_view_enabled={enabled} display_time_enabled={enabled} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x2A and frame.payload:
        return f"metric_system={frame.payload[0]} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x2D and frame.payload:
        return f"sedentary_reminder_enabled={frame.payload[0] == 1} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x2E and frame.payload:
        return f"device_version={frame.payload[0]}"
    if frame.command == 0x24 and frame.payload:
        return f"dominant_hand={frame.payload[0]} payload={hex_bytes(frame.payload)}"
    if frame.command == 0x33:
        return decode_history_step_sleep_marker(frame.payload)
    if frame.command == 0x37:
        return f"movement_heart_rate payload={hex_bytes(frame.payload)}"
    if frame.command == 0x3D:
        return f"last_24h_blood_pressure payload={hex_bytes(frame.payload)}"
    if frame.command == 0x3E:
        return f"last_24h_blood_oxygen payload={hex_bytes(frame.payload)}"
    if frame.command == 0x6E:
        return decode_watch_face_background_transfer(frame.payload)
    if frame.command == 0x74:
        return decode_store_watch_face_transfer(frame.payload)
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
    if frame.command == 0xB9:
        return decode_new_alarm_list(frame.payload)
    if frame.command == 0xBA:
        return decode_package_length(frame.payload)
    if frame.command == 0xBB:
        return decode_bb_subcommand(frame.payload)
    if frame.command == 0x84:
        return decode_support_watch_faces(frame.payload)
    if frame.command == 0x81:
        return decode_period_time("do_not_disturb_time", frame.payload)
    if frame.command == 0x82:
        return decode_period_time("quick_view_time", frame.payload)
    if frame.command == 0x83:
        return decode_sedentary_period(frame.payload)
    if frame.command == 0x87:
        return decode_reminder_period_group(frame.payload)
    if frame.command == 0x8D:
        return decode_single_byte("display_time", frame.payload)
    if frame.command == 0xAC:
        return decode_single_byte("tap_to_wake", frame.payload, boolean=True)
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


def decode_period_time(label: str, payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) < 4:
        return f"{label} payload={hex_bytes(payload)}"
    return (
        f"{label} start={payload[0]:02d}:{payload[1]:02d} "
        f"end={payload[2]:02d}:{payload[3]:02d} payload={hex_bytes(payload)}"
    )


def decode_single_byte(label: str, payload: bytes, boolean: bool = False) -> str | None:
    payload = bytes(payload)
    if not payload:
        return f"{label}=<empty>"
    value: int | bool = payload[0] == 1 if boolean else payload[0]
    return f"{label}={value} payload={hex_bytes(payload)}"


def decode_sedentary_period(payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) < 4:
        return f"sedentary_reminder_period payload={hex_bytes(payload)}"
    return (
        f"sedentary_reminder_period period={payload[0]} steps={payload[1]} "
        f"start_hour={payload[2]} end_hour={payload[3]} payload={hex_bytes(payload)}"
    )


def decode_reminder_period_group(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    labels = {
        1: "drink_water_reminder",
        3: "hand_washing_reminder",
    }
    label = labels.get(payload[0], f"reminder_group_{payload[0]}")
    if len(payload) >= 6:
        return (
            f"{label} enabled={payload[1] == 1} start={payload[2]:02d}:{payload[3]:02d} "
            f"count={payload[4]} period={payload[5]} payload={hex_bytes(payload)}"
        )
    return f"{label} payload={hex_bytes(payload)}"


def decode_bb_subcommand(payload: bytes) -> str | None:
    payload = bytes(payload)
    if len(payload) < 2:
        return f"bb_subcommand payload={hex_bytes(payload)}"
    group = payload[0]
    subcommand = payload[1]
    data = payload[2:]
    if group == 4 and subcommand == 6:
        if len(data) >= 6:
            return (
                f"new_drink_water_reminder enabled={data[1] == 1} "
                f"start={data[2]:02d}:{data[3]:02d} count={data[4]} "
                f"period={data[5]} payload={hex_bytes(payload)}"
            )
        return f"new_drink_water_reminder payload={hex_bytes(payload)}"
    if group == 12 and subcommand == 0:
        if data:
            return f"screen_off_clock_enabled={data[0] == 1} payload={hex_bytes(payload)}"
        return f"screen_off_clock_state payload={hex_bytes(payload)}"
    if group == 12 and subcommand == 2:
        if len(data) >= 4:
            return (
                f"screen_off_clock_time start={data[0]:02d}:{data[1]:02d} "
                f"end={data[2]:02d}:{data[3]:02d} payload={hex_bytes(payload)}"
            )
        return f"screen_off_clock_time payload={hex_bytes(payload)}"
    return f"bb_group={group} subcommand={subcommand} payload={hex_bytes(data)}"


def decode_alarm_list(payload: bytes) -> str | None:
    alarms = parse_alarm_list(payload)
    if alarms is None:
        return f"alarm_list payload={hex_bytes(payload)}"
    return "alarm_list alarms=[" + ", ".join(_alarm_display(alarm) for alarm in alarms) + "]"


def decode_new_alarm_list(payload: bytes) -> str | None:
    alarms = parse_new_alarm_list(payload)
    if alarms is None:
        return f"new_alarm_list payload={hex_bytes(payload)}"
    return "new_alarm_list alarms=[" + ", ".join(_alarm_display(alarm) for alarm in alarms) + "]"


def _alarm_display(alarm: AlarmInfo) -> str:
    date = f" date={alarm.date}" if alarm.date else ""
    return (
        f"id={alarm.id} enabled={alarm.enabled} time={alarm.hour:02d}:{alarm.minute:02d} "
        f"repeat={alarm.repeat_mode}{date}"
    )


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
    subcommand = payload[0]
    if subcommand == 1:
        records = _decode_training_list(payload)
        if records is not None:
            return f"history_training_list records={records}"
    if subcommand == 3:
        detail = _decode_training_detail(payload)
        if detail is not None:
            return f"history_training_detail {detail}"
    if subcommand in {5, 8, 10}:
        chunk = _decode_training_series_chunk(payload)
        if chunk is not None:
            labels = {5: "heart_rate", 8: "steps", 10: "distance"}
            return f"history_training_{labels[subcommand]} {chunk}"

    labels = {
        0: "history_training_list_request",
        1: "history_training_list",
        2: "history_training_detail_request",
        3: "history_training_detail",
        4: "history_training_heart_rate_request",
        5: "history_training_heart_rate",
        6: "history_training_list_prepare",
        7: "history_training_steps_request",
        8: "history_training_steps",
        9: "history_training_distance_request",
        10: "history_training_distance",
    }
    label = labels.get(subcommand, "training_subcommand")
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
    if payload[0] == 1 and len(payload) >= 5:
        offset = int.from_bytes(payload[1:5], byteorder="little", signed=False)
        return f"file_transfer_offset offset={offset}"
    if payload[0] == 2:
        crc = parse_file_transfer_crc(payload)
        if crc is not None:
            return f"file_transfer_crc crc=0x{crc:04X} payload={hex_bytes(payload)}"
        return f"file_transfer_crc payload={hex_bytes(payload)}"
    return f"{labels.get(payload[0], 'file_transfer')} payload={hex_bytes(payload)}"


def decode_watch_face_background_transfer(payload: bytes) -> str | None:
    payload = bytes(payload)
    index = parse_store_watch_face_offset(payload)
    if index is not None:
        return f"watch_face_background_chunk_index index={index}"
    offset = parse_file_transfer_offset(payload)
    if offset is not None:
        return f"watch_face_background_offset offset={offset}"
    crc = parse_file_transfer_crc(payload)
    if crc is not None:
        return f"watch_face_background_crc crc=0x{crc:04X} payload={hex_bytes(payload)}"
    if len(payload) != 4:
        return f"watch_face_background_transfer payload={hex_bytes(payload)}"
    if payload == b"\x00\x00\x00\x00":
        return "watch_face_background_check_ok"
    if payload == b"\xFF\xFF\xFF\xFF":
        return "watch_face_background_check_failed"
    size = int.from_bytes(payload, byteorder="big", signed=False)
    return f"watch_face_background_size size={size}"


def decode_store_watch_face_transfer(payload: bytes) -> str | None:
    offset = parse_store_watch_face_offset(payload)
    if offset is not None:
        return f"store_watch_face_offset index={offset}"
    crc = parse_store_watch_face_crc(payload)
    if crc is not None:
        return f"store_watch_face_crc crc=0x{crc:04X}"
    if len(payload) == 4 and payload[0] == 0x00:
        size = int.from_bytes(payload[1:4], byteorder="big", signed=False)
        return f"store_watch_face_prepare size={size}"
    return f"store_watch_face_transfer payload={hex_bytes(payload)}"


def decode_package_length(payload: bytes) -> str | None:
    packet_length = parse_package_length(payload)
    if packet_length is None:
        return None
    return f"package_length={packet_length}"


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


def _decode_training_list(payload: bytes) -> list[str] | None:
    if len(payload) % 5 != 1:
        return None
    records = []
    for offset in range(1, len(payload), 5):
        timestamp = int.from_bytes(payload[offset : offset + 4], "little")
        if timestamp <= 1:
            continue
        record_id = offset // 5
        training_type = payload[offset + 4]
        records.append(f"id={record_id} type={training_type} start={_format_timestamp(timestamp)}")
    return records


def _decode_training_detail(payload: bytes) -> str | None:
    if len(payload) < 26:
        return None
    training_id = payload[1]
    start = int.from_bytes(payload[2:6], "little")
    end = int.from_bytes(payload[6:10], "little")
    valid_time = int.from_bytes(payload[10:12], "little")
    training_type = payload[13]
    steps = int.from_bytes(payload[14:18], "little")
    distance = int.from_bytes(payload[18:22], "little")
    calories = int.from_bytes(payload[22:24], "little")
    return (
        f"id={training_id} type={training_type} "
        f"start={_format_timestamp(start)} end={_format_timestamp(end)} "
        f"valid_time={valid_time} steps={steps} distance={distance} calories={calories} "
        f"payload={hex_bytes(payload)}"
    )


def _decode_training_series_chunk(payload: bytes) -> str | None:
    if len(payload) < 4:
        return None
    subcommand = payload[0]
    training_id = payload[1]
    offset = int.from_bytes(payload[2:4], "big")
    complete = offset == 0xFFFF
    data = payload[4:]
    if subcommand == 5:
        values = [value if 40 <= value <= 200 else 0 for value in data]
    elif subcommand == 10:
        if len(data) % 2 != 0:
            return None
        values = [
            int.from_bytes(data[index : index + 2], "little")
            for index in range(0, len(data), 2)
        ]
    else:
        values = list(data)
    nonzero_count = sum(1 for value in values if value != 0)
    trimmed_count = _trimmed_count(values)
    return (
        f"id={training_id} next_offset={offset} complete={complete} "
        f"count={len(values)} nonzero_count={nonzero_count} trimmed_count={trimmed_count} "
        f"values={values} payload={hex_bytes(payload)}"
    )


def _trimmed_count(values: list[int]) -> int:
    for index in range(len(values) - 1, -1, -1):
        if values[index] != 0:
            return index + 1
    return 0


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
    support = parse_support_watch_faces(payload)
    if support is None:
        return None
    return (
        f"support_watch_faces=display_index={support.display_index} "
        f"supported={support.supported}"
    )


def decode_watch_face_subcommand(payload: bytes) -> str | None:
    payload = bytes(payload)
    if not payload:
        return None
    subcommand = payload[0]
    data = payload[1:]
    screen = parse_watch_face_screen(payload)
    if screen is not None:
        return (
            "watch_face_screen="
            f"width={screen.width} height={screen.height} corner={screen.corner} "
            f"thumb_width={screen.thumb_width} thumb_height={screen.thumb_height} "
            f"thumb_corner={screen.thumb_corner}"
        )
    if subcommand == 0 and len(data) >= 2:
        display_index = (data[0] << 8) + data[1]
        supported = list(data[2:])
        return f"watch_face_subcommand=0x00 display_index={display_index} supported={supported}"
    return f"watch_face_subcommand=0x{subcommand:02X} payload={hex_bytes(data)}"


def decode_watch_face_list(payload: bytes) -> list[WatchFaceSlot] | None:
    return parse_watch_face_list(payload)


def parse_display_watch_face(payload: bytes) -> int | None:
    payload = bytes(payload)
    if not payload:
        return None
    return payload[0]


def parse_support_watch_faces(payload: bytes) -> WatchFaceSupport | None:
    payload = bytes(payload)
    if len(payload) < 2:
        return None
    display_index = (payload[0] << 8) + payload[1]
    return WatchFaceSupport(display_index=display_index, supported=list(payload[2:]))


def parse_watch_face_screen(payload: bytes) -> WatchFaceScreen | None:
    payload = bytes(payload)
    if len(payload) < 13 or payload[0] != 20:
        return None
    data = payload[1:]
    values = [
        data[0] + (data[1] << 8),
        data[2] + (data[3] << 8),
        data[4] + (data[5] << 8),
        data[6] + (data[7] << 8),
        data[8] + (data[9] << 8),
        data[10] + (data[11] << 8),
    ]
    return WatchFaceScreen(
        width=values[0],
        height=values[1],
        corner=values[2],
        thumb_width=values[3],
        thumb_height=values[4],
        thumb_corner=values[5],
    )


def parse_watch_face_list(payload: bytes) -> list[WatchFaceSlot] | None:
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


def parse_alarm_list(payload: bytes, offset: int = 0, strict_ids: bool = False) -> list[AlarmInfo] | None:
    payload = bytes(payload)
    if len(payload) <= offset or (len(payload) - offset) % 8 != 0:
        return None
    alarms: list[AlarmInfo] = []
    for record_offset in range(offset, len(payload), 8):
        record = payload[record_offset : record_offset + 8]
        alarm_id = record[0]
        if not strict_ids and alarm_id == 0:
            alarm_id = (record_offset - offset) // 8
        enabled = record[1] == 1
        raw_type = record[2]
        hour = record[3]
        minute = record[4]
        date_value = (record[5] << 8) + record[6]
        repeat = record[7]
        date = None
        if raw_type == 0:
            date = _alarm_date(date_value)
            repeat = 0
        elif raw_type == 1:
            repeat = 127
        alarms.append(
            AlarmInfo(
                id=alarm_id,
                enabled=enabled,
                hour=hour,
                minute=minute,
                repeat_mode=repeat,
                date=date,
                raw_type=raw_type,
            )
        )
    return alarms


def parse_new_alarm_list(payload: bytes) -> list[AlarmInfo] | None:
    payload = bytes(payload)
    if len(payload) == 3 and payload[:2] == bytes([0x15, 0x04]):
        return []
    if len(payload) <= 3:
        return None
    return parse_alarm_list(payload, offset=3, strict_ids=True)


def encode_alarm_record(alarm: AlarmInfo) -> bytes:
    if not 0 <= alarm.id <= 0xFF:
        raise ValueError(f"alarm id must fit in one byte: {alarm.id}")
    if not 0 <= alarm.hour <= 23:
        raise ValueError(f"alarm hour out of range: {alarm.hour}")
    if not 0 <= alarm.minute <= 59:
        raise ValueError(f"alarm minute out of range: {alarm.minute}")
    if not 0 <= alarm.repeat_mode <= 0xFF:
        raise ValueError(f"alarm repeat mode must fit in one byte: {alarm.repeat_mode}")

    if alarm.date is not None:
        raw_type = 0
        date_value = _encode_alarm_date(alarm.date)
        repeat = 0
    elif alarm.raw_type is not None:
        if not 0 <= alarm.raw_type <= 0xFF:
            raise ValueError(f"alarm raw type must fit in one byte: {alarm.raw_type}")
        raw_type = alarm.raw_type
        date_value = 0
        repeat = alarm.repeat_mode
    elif alarm.repeat_mode == 127:
        raw_type = 1
        date_value = 0
        repeat = 127
    else:
        raw_type = 2
        date_value = 0
        repeat = alarm.repeat_mode

    return bytes(
        [
            alarm.id,
            1 if alarm.enabled else 0,
            raw_type,
            alarm.hour,
            alarm.minute,
            (date_value >> 8) & 0xFF,
            date_value & 0xFF,
            repeat,
        ]
    )


def _alarm_date(value: int) -> str | None:
    if value == 0:
        return None
    year = ((value >> 12) & 0x0F) + 2015
    month = (value >> 8) & 0x0F
    day = value & 0xFF
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _encode_alarm_date(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"alarm date must be YYYY-MM-DD: {value!r}") from exc
    year_offset = parsed.year - 2015
    if not 0 <= year_offset <= 0x0F:
        raise ValueError(f"alarm date year must be in 2015-2030: {value!r}")
    return (year_offset << 12) | (parsed.month << 8) | parsed.day


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def set_display_watch_face_packet(index: int) -> Packet:
    if not 0 <= index <= 0xFF:
        raise ValueError(f"watch-face index must fit in one byte: {index}")
    return Packet(0x19, bytes([index]))


def set_goal_steps_packet(steps: int) -> Packet:
    if not 0 <= steps <= 0xFFFFFFFF:
        raise ValueError(f"goal steps must fit in uint32: {steps}")
    return Packet(0x16, steps.to_bytes(4, "big"))


def set_time_system_packet(value: int) -> Packet:
    if value not in {0, 1}:
        raise ValueError(f"time system must be 0 or 1: {value}")
    return Packet(0x17, bytes([value]))


def set_display_time_packet(enabled: bool) -> Packet:
    return Packet(0x18, bytes([1 if enabled else 0]))


def set_do_not_disturb_time_packet(
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
) -> Packet:
    for label, value, limit in (
        ("start_hour", start_hour, 23),
        ("start_minute", start_minute, 59),
        ("end_hour", end_hour, 23),
        ("end_minute", end_minute, 59),
    ):
        if not 0 <= value <= limit:
            raise ValueError(f"{label} out of range: {value}")
    return Packet(0x71, bytes([start_hour, start_minute, end_hour, end_minute]))


def set_legacy_alarm_packet(alarm: AlarmInfo) -> Packet:
    return Packet(0x11, encode_alarm_record(alarm))


def set_new_alarm_packet(alarm: AlarmInfo) -> Packet:
    return Packet(0xB9, bytes([0x05, 0x00]) + encode_alarm_record(alarm))


def delete_new_alarm_packet(alarm_id: int) -> Packet:
    if not 0 <= alarm_id <= 0xFF:
        raise ValueError(f"alarm id must fit in one byte: {alarm_id}")
    return Packet(0xB9, bytes([0x05, 0x02, alarm_id]))


def delete_all_new_alarms_packet() -> Packet:
    return Packet(0xB9, bytes([0x05, 0x03]))


def set_current_time_packet(timestamp: int, timezone_marker: int = 8) -> Packet:
    if not 0 <= timestamp <= 0xFFFFFFFF:
        raise ValueError(f"timestamp must fit in uint32: {timestamp}")
    if not 0 <= timezone_marker <= 0xFF:
        raise ValueError(f"timezone marker must fit in one byte: {timezone_marker}")
    return Packet(0x31, timestamp.to_bytes(4, "big") + bytes([timezone_marker]))


def set_timezone_packet(offset_seconds: int) -> Packet:
    if not -(2**31) <= offset_seconds < 2**31:
        raise ValueError(f"timezone offset must fit in int32: {offset_seconds}")
    return Packet(0xBB, bytes([0x07, 0x00]) + offset_seconds.to_bytes(4, "little", signed=True))


def query_training_detail_packet(training_id: int) -> Packet:
    if not 0 <= training_id <= 0xFF:
        raise ValueError(f"training id must fit in one byte: {training_id}")
    return Packet(0xB2, bytes([0x02, training_id]))


def query_training_series_packet(training_id: int, kind: str, offset: int = 0) -> Packet:
    if not 0 <= training_id <= 0xFF:
        raise ValueError(f"training id must fit in one byte: {training_id}")
    if not 0 <= offset <= 0xFFFF:
        raise ValueError(f"training series offset must fit in uint16: {offset}")
    commands = {
        "heart-rate": 0x04,
        "hr": 0x04,
        "steps": 0x07,
        "distance": 0x09,
    }
    command = commands.get(kind)
    if command is None:
        raise ValueError(f"unknown training series kind: {kind}")
    return Packet(0xB2, bytes([command, training_id]) + offset.to_bytes(2, "big"))


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


def file_transfer_check_packet(ok: bool) -> Packet:
    return Packet(0xB7, bytes([0x03 if ok else 0x04]))


def file_transfer_abort_packet() -> Packet:
    return Packet(0xB7, bytes([0x05]))


def watch_face_background_size_packet(size: int) -> Packet:
    if not 0 <= size <= 0xFFFFFFFF:
        raise ValueError(f"background size must fit in uint32: {size}")
    return Packet(0x6E, size.to_bytes(4, byteorder="big"))


def watch_face_background_check_packet(ok: bool) -> Packet:
    return Packet(0x6E, b"\x00\x00\x00\x00" if ok else b"\xFF\xFF\xFF\xFF")


def store_watch_face_prepare_packet(size: int) -> Packet:
    if not 0 <= size <= 0xFFFFFF:
        raise ValueError(f"store watch-face size must fit in 24 bits: {size}")
    return Packet(0x74, bytes([0x00]) + size.to_bytes(3, byteorder="big"))


def store_watch_face_check_packet(ok: bool) -> Packet:
    return Packet(0x74, bytes([0x00 if ok else 0x01, 0x00, 0x00, 0x00]))


def parse_package_length(payload: bytes) -> int | None:
    payload = bytes(payload)
    if len(payload) >= 3 and payload[0] == 0x01:
        return int.from_bytes(payload[1:3], byteorder="little", signed=False)
    return None


def parse_file_transfer_offset(payload: bytes) -> int | None:
    payload = bytes(payload)
    if len(payload) >= 5 and payload[0] == 0x01:
        return int.from_bytes(payload[1:5], byteorder="little", signed=False)
    return None


def parse_file_transfer_crc(payload: bytes) -> int | None:
    payload = bytes(payload)
    if len(payload) >= 5 and payload[0] == 0x02:
        return int.from_bytes(payload[3:5], byteorder="big", signed=False)
    if len(payload) >= 3 and payload[0] == 0x02:
        return int.from_bytes(payload[1:3], byteorder="big", signed=False)
    return None


def parse_store_watch_face_offset(payload: bytes) -> int | None:
    payload = bytes(payload)
    if len(payload) == 2:
        return int.from_bytes(payload, byteorder="big", signed=False)
    return None


def parse_store_watch_face_crc(payload: bytes) -> int | None:
    payload = bytes(payload)
    if len(payload) == 4 and payload[:2] == b"\xFF\xFF":
        return int.from_bytes(payload[2:4], byteorder="big", signed=False)
    return None


SET_DISPLAY_WATCH_FACE_COMMAND = 0x19
QUERY_FILE_TRANSFER_PACKET_LENGTH = Packet(0xBA, bytes([0x01]))
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
QUERY_TIME_SYSTEM = Packet(0x27)
QUERY_QUICK_VIEW = Packet(0x28)
QUERY_DISPLAY_TIME = QUERY_QUICK_VIEW
QUERY_DISPLAY_TIME_DURATION = Packet(0x8D)
QUERY_DO_NOT_DISTURB_TIME = Packet(0x81)
QUERY_DOMINANT_HAND = Packet(0x24)
QUERY_METRIC_SYSTEM = Packet(0x2A)
QUERY_SEDENTARY_REMINDER = Packet(0x2D)
QUERY_SEDENTARY_REMINDER_PERIOD = Packet(0x83)
QUERY_QUICK_VIEW_TIME = Packet(0x82)
QUERY_DRINK_WATER_REMINDER = Packet(0x87, bytes([0x01]))
QUERY_HAND_WASHING_REMINDER = Packet(0x87, bytes([0x03]))
QUERY_NEW_DRINK_WATER_REMINDER = Packet(0xBB, bytes([0x04, 0x06, 0x01]))
QUERY_SCREEN_OFF_CLOCK_STATE = Packet(0xBB, bytes([0x0C, 0x00]))
QUERY_SCREEN_OFF_CLOCK_TIME = Packet(0xBB, bytes([0x0C, 0x02]))
QUERY_TAP_TO_WAKE = Packet(0xAC)
QUERY_ALARMS = Packet(0x21)
QUERY_NEW_ALARMS = Packet(0xB9, bytes([0x15, 0x04]))
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

SETTINGS_BASIC_QUERY_PACKETS = [
    QUERY_GOAL_STEP,
    QUERY_TIME_SYSTEM,
    QUERY_DISPLAY_TIME,
    QUERY_DO_NOT_DISTURB_TIME,
]

DAILY_SETTINGS_QUERY_PACKETS = [
    QUERY_DOMINANT_HAND,
    QUERY_METRIC_SYSTEM,
    QUERY_DISPLAY_TIME_DURATION,
    QUERY_QUICK_VIEW,
    QUERY_QUICK_VIEW_TIME,
    QUERY_SEDENTARY_REMINDER,
    QUERY_SEDENTARY_REMINDER_PERIOD,
    QUERY_DRINK_WATER_REMINDER,
    QUERY_NEW_DRINK_WATER_REMINDER,
    QUERY_HAND_WASHING_REMINDER,
    QUERY_SCREEN_OFF_CLOCK_STATE,
    QUERY_SCREEN_OFF_CLOCK_TIME,
    QUERY_TAP_TO_WAKE,
]

ALARM_QUERY_PACKETS = [
    QUERY_ALARMS,
    QUERY_NEW_ALARMS,
]

QUERY_SETS = {
    "alarms": ALARM_QUERY_PACKETS,
    "daily-settings": DAILY_SETTINGS_QUERY_PACKETS,
    "default": DEFAULT_QUERY_PACKETS,
    "health-basic": HEALTH_BASIC_QUERY_PACKETS,
    "health-extended": HEALTH_EXTENDED_QUERY_PACKETS,
    "health-history": HEALTH_HISTORY_QUERY_PACKETS,
    "settings-basic": SETTINGS_BASIC_QUERY_PACKETS,
    "watchface": WATCH_FACE_QUERY_PACKETS,
    "watchface-support": WATCH_FACE_SUPPORT_QUERY_PACKETS,
}

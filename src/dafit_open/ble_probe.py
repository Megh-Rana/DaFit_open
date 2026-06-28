"""Experimental BLE scanner/prober for CRP/Da Fit compatible watches."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .protocol import (
    ALT_CHARACTERISTIC_4A02,
    BATTERY_LEVEL,
    CRP_HISILICON,
    CRP_FEE4,
    CRP_NOTIFY_EXT_1,
    CRP_NOTIFY_EXT_2,
    CRP_NOTIFY_PRIMARY,
    CRP_NOTIFY_SECONDARY,
    CRP_WRITE_PRIMARY,
    HEART_RATE_MEASUREMENT,
    Packet,
    QUERY_DISPLAY_WATCH_FACE,
    QUERY_SETS,
    decode_frame,
    hex_bytes,
    parse_frame,
    query_training_detail_packet,
    set_display_watch_face_packet,
)


NOTIFY_UUIDS = {
    CRP_NOTIFY_PRIMARY,
    CRP_NOTIFY_SECONDARY,
    CRP_FEE4,
    CRP_NOTIFY_EXT_1,
    CRP_NOTIFY_EXT_2,
    CRP_HISILICON,
    BATTERY_LEVEL,
    HEART_RATE_MEASUREMENT,
    ALT_CHARACTERISTIC_4A02,
}


GATT_NAMES = {
    "00001800-0000-1000-8000-00805f9b34fb": "Generic Access",
    "00001801-0000-1000-8000-00805f9b34fb": "Generic Attribute",
    "0000180a-0000-1000-8000-00805f9b34fb": "Device Information",
    "0000180d-0000-1000-8000-00805f9b34fb": "Heart Rate",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery",
    "00002a00-0000-1000-8000-00805f9b34fb": "Device Name",
    "00002a01-0000-1000-8000-00805f9b34fb": "Appearance",
    "00002a04-0000-1000-8000-00805f9b34fb": "Peripheral Preferred Connection Parameters",
    "00002a19-0000-1000-8000-00805f9b34fb": "Battery Level",
    "00002a23-0000-1000-8000-00805f9b34fb": "System ID",
    "00002a24-0000-1000-8000-00805f9b34fb": "Model Number",
    "00002a25-0000-1000-8000-00805f9b34fb": "Serial Number",
    "00002a26-0000-1000-8000-00805f9b34fb": "Firmware Revision",
    "00002a27-0000-1000-8000-00805f9b34fb": "Hardware Revision",
    "00002a28-0000-1000-8000-00805f9b34fb": "Software Revision",
    "00002a29-0000-1000-8000-00805f9b34fb": "Manufacturer Name",
    "00002a2a-0000-1000-8000-00805f9b34fb": "IEEE Regulatory Certification Data List",
    "00002a37-0000-1000-8000-00805f9b34fb": "Heart Rate Measurement",
    "00002a38-0000-1000-8000-00805f9b34fb": "Body Sensor Location",
    "00002a39-0000-1000-8000-00805f9b34fb": "Heart Rate Control Point",
    "00002a50-0000-1000-8000-00805f9b34fb": "PnP ID",
    "00002aa6-0000-1000-8000-00805f9b34fb": "Central Address Resolution",
    "00002b3a-0000-1000-8000-00805f9b34fb": "Server Supported Features",
    "000001ff-3c17-d293-8e48-14fe2e4da212": "Auxiliary Data Service",
    "000002fd-3c17-d293-8e48-14fe2e4da212": "Auxiliary Transfer Service",
    "0000d0ff-3c17-d293-8e48-14fe2e4da212": "Private D0FF Service",
    "0000feea-0000-1000-8000-00805f9b34fb": "CRP Control Service",
    "0000fee1-0000-1000-8000-00805f9b34fb": "CRP Primary Notify/Status",
    "0000fee2-0000-1000-8000-00805f9b34fb": "CRP Primary Write",
    "0000fee3-0000-1000-8000-00805f9b34fb": "CRP Secondary Notify",
    "0000fee4-0000-1000-8000-00805f9b34fb": "CRP Device Address",
    "0000fee5-0000-1000-8000-00805f9b34fb": "CRP Command Write",
    "0000fee6-0000-1000-8000-00805f9b34fb": "CRP Command Write",
    "0000fea1-0000-1000-8000-00805f9b34fb": "Auxiliary Status",
    "0000fec9-0000-1000-8000-00805f9b34fb": "Auxiliary Device Address",
    "0000fd03-0000-1000-8000-00805f9b34fb": "Auxiliary Transfer Write",
    "0000fd04-0000-1000-8000-00805f9b34fb": "Auxiliary Transfer Notify",
    "0000ff02-0000-1000-8000-00805f9b34fb": "Auxiliary Data Write",
    "0000ff03-0000-1000-8000-00805f9b34fb": "Auxiliary Data Notify",
    "0000ff04-0000-1000-8000-00805f9b34fb": "Auxiliary Data Control",
    "0000ffd1-0000-1000-8000-00805f9b34fb": "D0FF Write",
    "0000ffd2-0000-1000-8000-00805f9b34fb": "D0FF Device Address Mirror",
    "0000ffd3-0000-1000-8000-00805f9b34fb": "D0FF Read Slot",
    "0000ffd4-0000-1000-8000-00805f9b34fb": "D0FF Read Slot",
    "0000ffe0-0000-1000-8000-00805f9b34fb": "D0FF Table",
    "0000ffe1-0000-1000-8000-00805f9b34fb": "D0FF Empty Read",
    "0000fff1-0000-1000-8000-00805f9b34fb": "D0FF Info",
    "0000fff3-0000-1000-8000-00805f9b34fb": "D0FF Short Value",
    "0000fff4-0000-1000-8000-00805f9b34fb": "D0FF Table",
    "0000fff5-0000-1000-8000-00805f9b34fb": "D0FF Empty Read",
}


TEXT_CHARACTERISTICS = {
    "00002a00-0000-1000-8000-00805f9b34fb",
    "00002a24-0000-1000-8000-00805f9b34fb",
    "00002a25-0000-1000-8000-00805f9b34fb",
    "00002a26-0000-1000-8000-00805f9b34fb",
    "00002a27-0000-1000-8000-00805f9b34fb",
    "00002a28-0000-1000-8000-00805f9b34fb",
    "00002a29-0000-1000-8000-00805f9b34fb",
}


MAC_CHARACTERISTICS = {
    "0000fec9-0000-1000-8000-00805f9b34fb",
    "0000fee4-0000-1000-8000-00805f9b34fb",
}


PRIVATE_TABLE_CHARACTERISTICS = {
    "0000ffe0-0000-1000-8000-00805f9b34fb",
    "0000fff4-0000-1000-8000-00805f9b34fb",
}


async def scan(timeout: float = 10.0, verbose: bool = False) -> None:
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for device, adv in devices.values():
        name = device.name or adv.local_name or "<unknown>"
        uuids = ", ".join(adv.service_uuids or [])
        print(f"{device.address}  RSSI={adv.rssi:>4}  {name}")
        if uuids:
            print(f"  services: {uuids}")
        if verbose:
            if adv.tx_power is not None:
                print(f"  tx_power: {adv.tx_power}")
            if adv.manufacturer_data:
                for company, value in adv.manufacturer_data.items():
                    print(f"  manufacturer[{company:#06x}]: {hex_bytes(value)}")
            if adv.service_data:
                for uuid, value in adv.service_data.items():
                    print(f"  service_data[{uuid}]: {hex_bytes(value)}")
            if adv.platform_data:
                print(f"  platform_data: {adv.platform_data!r}")


async def probe(
    address: str,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    query_set: str = "default",
    json_out: str | None = None,
) -> None:
    capture = _new_capture(
        "probe",
        address,
        {
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
            "query_set": query_set,
        },
    )
    device: BLEDevice | str
    if direct:
        print(f"using direct address connection for {address}")
        device = address
    else:
        found_device = await _find_device(address, scan_timeout)
        if found_device is None:
            print(f"device not found during {scan_timeout:.1f}s scan: {address}")
            _write_capture(json_out, capture)
            return
        device = found_device
        capture["device"] = _device_snapshot(device)

    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"connecting to {_device_label(device)}, attempt {attempt}/{retries}")
            capture["attempts"].append({"attempt": attempt, "device": _device_label(device)})
            await _probe_device(device, timeout, pair=pair, query_set=query_set, capture=capture)
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"connect/probe failed: {type(exc).__name__}: {exc}")
            capture["errors"].append(
                {"attempt": attempt, "type": type(exc).__name__, "message": str(exc)}
            )

        if attempt < retries:
            await asyncio.sleep(2)
            if not direct:
                refreshed = await _find_device(address, scan_timeout)
                if refreshed is not None:
                    device = refreshed
                    capture["device"] = _device_snapshot(refreshed)

    print("probe failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def device_info(
    address: str,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    capture = _new_capture(
        "device-info",
        address,
        {
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    device: BLEDevice | str
    if direct:
        print(f"using direct address connection for {address}")
        device = address
    else:
        found_device = await _find_device(address, scan_timeout)
        if found_device is None:
            print(f"device not found during {scan_timeout:.1f}s scan: {address}")
            _write_capture(json_out, capture)
            return
        device = found_device
        capture["device"] = _device_snapshot(device)

    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"connecting to {_device_label(device)}, attempt {attempt}/{retries}")
            capture["attempts"].append({"attempt": attempt, "device": _device_label(device)})
            await _read_device_info(device, timeout, pair=pair, capture=capture)
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"device-info failed: {type(exc).__name__}: {exc}")
            capture["errors"].append(
                {"attempt": attempt, "type": type(exc).__name__, "message": str(exc)}
            )

        if attempt < retries:
            await asyncio.sleep(2)
            if not direct:
                refreshed = await _find_device(address, scan_timeout)
                if refreshed is not None:
                    device = refreshed
                    capture["device"] = _device_snapshot(refreshed)

    print("device-info failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def set_watch_face(
    address: str,
    index: int,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    if not 0 <= index <= 0xFF:
        raise ValueError(f"watch-face index must be between 0 and 255: {index}")

    capture = _new_capture(
        "set-watch-face",
        address,
        {
            "index": index,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    device: BLEDevice | str
    if direct:
        print(f"using direct address connection for {address}")
        device = address
    else:
        found_device = await _find_device(address, scan_timeout)
        if found_device is None:
            print(f"device not found during {scan_timeout:.1f}s scan: {address}")
            _write_capture(json_out, capture)
            return
        device = found_device
        capture["device"] = _device_snapshot(device)

    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"connecting to {_device_label(device)}, attempt {attempt}/{retries}")
            capture["attempts"].append({"attempt": attempt, "device": _device_label(device)})
            await _set_watch_face_device(device, index, timeout, pair=pair, capture=capture)
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"set-watch-face failed: {type(exc).__name__}: {exc}")
            capture["errors"].append(
                {"attempt": attempt, "type": type(exc).__name__, "message": str(exc)}
            )

        if attempt < retries:
            await asyncio.sleep(2)
            if not direct:
                refreshed = await _find_device(address, scan_timeout)
                if refreshed is not None:
                    device = refreshed
                    capture["device"] = _device_snapshot(refreshed)

    print("set-watch-face failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def training_detail(
    address: str,
    training_ids: list[int],
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    for training_id in training_ids:
        if not 0 <= training_id <= 0xFF:
            raise ValueError(f"training id must be between 0 and 255: {training_id}")

    capture = _new_capture(
        "training-detail",
        address,
        {
            "training_ids": training_ids,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    device: BLEDevice | str
    if direct:
        print(f"using direct address connection for {address}")
        device = address
    else:
        found_device = await _find_device(address, scan_timeout)
        if found_device is None:
            print(f"device not found during {scan_timeout:.1f}s scan: {address}")
            _write_capture(json_out, capture)
            return
        device = found_device
        capture["device"] = _device_snapshot(device)

    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"connecting to {_device_label(device)}, attempt {attempt}/{retries}")
            capture["attempts"].append({"attempt": attempt, "device": _device_label(device)})
            await _training_detail_device(device, training_ids, timeout, pair=pair, capture=capture)
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"training-detail failed: {type(exc).__name__}: {exc}")
            capture["errors"].append(
                {"attempt": attempt, "type": type(exc).__name__, "message": str(exc)}
            )

        if attempt < retries:
            await asyncio.sleep(2)
            if not direct:
                refreshed = await _find_device(address, scan_timeout)
                if refreshed is not None:
                    device = refreshed
                    capture["device"] = _device_snapshot(refreshed)

    print("training-detail failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def _probe_device(
    device: BLEDevice | str,
    timeout: float,
    pair: bool,
    query_set: str,
    capture: dict[str, Any],
) -> None:
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        write_char = None
        write_with_response = True
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    write_char = char
                    write_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; stopping after discovery")
            return

        await _send_queries(
            client,
            write_char,
            write_with_response=write_with_response,
            mtu_payload=_guess_mtu_payload(client),
            query_set=query_set,
            capture=capture,
        )
        await asyncio.sleep(5)

        for char in notify_chars:
            await client.stop_notify(char)


async def _set_watch_face_device(
    device: BLEDevice | str,
    index: int,
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        write_char = None
        write_with_response = True
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    write_char = char
                    write_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; cannot set watch face")
            return

        print(f"setting display watch-face slot: {index}")
        await _write_packet(
            client,
            write_char,
            set_display_watch_face_packet(index),
            write_with_response,
            _guess_mtu_payload(client),
            capture,
        )
        await asyncio.sleep(1)
        print("verifying display watch-face slot with cmd=0x29")
        await _write_packet(
            client,
            write_char,
            QUERY_DISPLAY_WATCH_FACE,
            write_with_response,
            _guess_mtu_payload(client),
            capture,
        )
        await asyncio.sleep(5)

        for char in notify_chars:
            await client.stop_notify(char)


async def _training_detail_device(
    device: BLEDevice | str,
    training_ids: list[int],
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        write_char = None
        write_with_response = True
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    write_char = char
                    write_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; cannot query training detail")
            return

        mtu_payload = _guess_mtu_payload(client)
        for training_id in training_ids:
            print(f"querying training detail id: {training_id}")
            await _write_packet(
                client,
                write_char,
                query_training_detail_packet(training_id),
                write_with_response,
                mtu_payload,
                capture,
            )
            await asyncio.sleep(0.75)
        await asyncio.sleep(5)

        for char in notify_chars:
            await client.stop_notify(char)


async def _read_device_info(
    device: BLEDevice | str,
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected
        services = client.services
        capture["services"] = _services_snapshot(services)

        for service in services:
            print(f"service {service.uuid} {GATT_NAMES.get(service.uuid.lower(), '')}".rstrip())
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                if "read" not in char.properties:
                    continue
                record: dict[str, Any] = {
                    "service_uuid": service.uuid.lower(),
                    "characteristic": _char_snapshot(char),
                }
                try:
                    raw = bytes(await client.read_gatt_char(char))
                    decoded = _decode_gatt_value(char.uuid, raw)
                    record["ok"] = True
                    record["value"] = decoded
                    print(f"    read {decoded['display']}")
                except Exception as exc:
                    record["ok"] = False
                    record["error"] = {"type": type(exc).__name__, "message": str(exc)}
                    print(f"    read failed: {type(exc).__name__}: {exc}")
                capture["reads"].append(record)


async def _find_device(address: str, timeout: float) -> BLEDevice | None:
    normalized = address.lower()
    print(f"scanning {timeout:.1f}s for {address} before connecting...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for device, adv in devices.values():
        if device.address.lower() == normalized:
            name = device.name or adv.local_name or "<unknown>"
            print(f"found {device.address} RSSI={adv.rssi} name={name}")
            return device
    return None


def _device_label(device: BLEDevice | str) -> str:
    if isinstance(device, str):
        return device
    return f"{device.address} ({device.name or '<unknown>'})"


def _notification_handler(sender: object, data: bytearray) -> None:
    _handle_notification(sender, data, capture=None)


def _make_notification_handler(capture: dict[str, Any]):
    def handler(sender: object, data: bytearray) -> None:
        _handle_notification(sender, data, capture=capture)

    return handler


def _handle_notification(
    sender: object,
    data: bytearray,
    capture: dict[str, Any] | None,
) -> None:
    raw = bytes(data)
    frame = parse_frame(raw)
    suffix = ""
    record: dict[str, Any] = {
        "timestamp": _utc_now(),
        "sender": str(sender),
        "hex": hex_bytes(raw),
    }
    if frame is not None:
        suffix = f"  frame flags=0x{frame.flags:02X} len={frame.packet_len} cmd=0x{frame.command:02X}"
        decoded = decode_frame(frame)
        record["frame"] = {
            "flags": frame.flags,
            "packet_len": frame.packet_len,
            "command": frame.command,
            "payload_hex": hex_bytes(frame.payload),
            "decoded": decoded,
        }
        if decoded:
            suffix += f"  {decoded}"
    if capture is not None:
        capture["notifications"].append(record)
    print(f"<< {sender}: {hex_bytes(raw)}{suffix}")


async def _send_queries(
    client: BleakClient,
    write_char: object,
    write_with_response: bool,
    mtu_payload: int,
    query_set: str,
    capture: dict[str, Any],
) -> None:
    packets = QUERY_SETS[query_set]
    print(f"query set: {query_set}")
    capture["query_set"] = query_set
    for packet in packets:
        await _write_packet(client, write_char, packet, write_with_response, mtu_payload, capture)
        await asyncio.sleep(0.5)


async def _write_packet(
    client: BleakClient,
    write_char: object,
    packet: Packet,
    write_with_response: bool,
    mtu_payload: int,
    capture: dict[str, Any],
) -> None:
    data = packet.__class__(packet.command, packet.payload, mtu_payload).build()
    print(f">> cmd=0x{packet.command:02X}: {hex_bytes(data)}")
    capture["sent_packets"].append(
        {
            "timestamp": _utc_now(),
            "command": packet.command,
            "payload_hex": hex_bytes(packet.payload),
            "hex": hex_bytes(data),
            "write_characteristic": _char_snapshot(write_char),
            "response": write_with_response,
        }
    )
    await client.write_gatt_char(write_char, data, response=write_with_response)


def _can_write(properties: Iterable[str]) -> bool:
    return "write" in properties or "write-without-response" in properties


def _guess_mtu_payload(client: BleakClient) -> int:
    # BlueZ warns when reading BleakClient.mtu_size before explicitly acquiring
    # MTU. Stay in the default 20-byte payload mode until we need large writes.
    return 20


def _new_capture(command: str, address: str, options: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dafit-open.capture.v1",
        "command": command,
        "address": address,
        "started_at": _utc_now(),
        "options": options,
        "device": None,
        "connected": False,
        "attempts": [],
        "services": [],
        "notifications_enabled": [],
        "sent_packets": [],
        "notifications": [],
        "reads": [],
        "errors": [],
    }


def _write_capture(path: str | None, capture: dict[str, Any]) -> None:
    if not path:
        return
    capture["finished_at"] = _utc_now()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(capture, indent=2, sort_keys=True) + "\n")
    print(f"wrote JSON capture: {destination}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _device_snapshot(device: BLEDevice) -> dict[str, Any]:
    return {
        "address": device.address,
        "name": device.name,
        "details": repr(getattr(device, "details", None)),
    }


def _services_snapshot(services: object) -> list[dict[str, Any]]:
    snapshot = []
    for service in services:
        snapshot.append(
            {
                "uuid": service.uuid.lower(),
                "name": GATT_NAMES.get(service.uuid.lower()),
                "handle": getattr(service, "handle", None),
                "characteristics": [_char_snapshot(char) for char in service.characteristics],
            }
        )
    return snapshot


def _char_snapshot(char: object) -> dict[str, Any]:
    uuid = str(getattr(char, "uuid", "")).lower()
    return {
        "uuid": uuid,
        "name": GATT_NAMES.get(uuid),
        "handle": getattr(char, "handle", None),
        "properties": list(getattr(char, "properties", [])),
    }


def _decode_gatt_value(uuid: str, raw: bytes) -> dict[str, Any]:
    uuid = uuid.lower()
    result: dict[str, Any] = {"hex": hex_bytes(raw), "bytes": list(raw)}
    if uuid in TEXT_CHARACTERISTICS:
        text = raw.decode("utf-8", errors="replace").rstrip("\x00").strip()
        display = "<empty>" if not raw else f"{text!r} ({hex_bytes(raw)})"
        result.update({"type": "text", "value": text, "display": display})
        return result
    if uuid == BATTERY_LEVEL and raw:
        result.update({"type": "uint8", "value": raw[0], "display": f"{raw[0]}% ({hex_bytes(raw)})"})
        return result
    if uuid in MAC_CHARACTERISTICS and len(raw) == 6:
        mac = _format_mac(raw)
        result.update({"type": "mac", "value": mac, "display": f"{mac} ({hex_bytes(raw)})"})
        return result
    if uuid == "0000ffd2-0000-1000-8000-00805f9b34fb" and len(raw) % 6 == 0:
        macs = [_format_mac(raw[offset : offset + 6]) for offset in range(0, len(raw), 6)]
        result.update({"type": "mac_list", "value": macs, "display": f"{macs} ({hex_bytes(raw)})"})
        return result
    if uuid == "00002a01-0000-1000-8000-00805f9b34fb" and len(raw) >= 2:
        value = _uint16_le(raw, 0)
        result.update(
            {
                "type": "appearance",
                "value": value,
                "display": f"{value} (0x{value:04X}, {hex_bytes(raw)})",
            }
        )
        return result
    if uuid == "00002a04-0000-1000-8000-00805f9b34fb" and len(raw) >= 8:
        min_interval = _uint16_le(raw, 0)
        max_interval = _uint16_le(raw, 2)
        latency = _uint16_le(raw, 4)
        supervision_timeout = _uint16_le(raw, 6)
        value = {
            "min_interval_units": min_interval,
            "max_interval_units": max_interval,
            "latency": latency,
            "supervision_timeout_units": supervision_timeout,
            "min_interval_ms": min_interval * 1.25,
            "max_interval_ms": max_interval * 1.25,
            "supervision_timeout_ms": supervision_timeout * 10,
        }
        result.update(
            {
                "type": "connection_parameters",
                "value": value,
                "display": (
                    "connection_parameters="
                    f"min={value['min_interval_ms']:.2f}ms "
                    f"max={value['max_interval_ms']:.2f}ms "
                    f"latency={latency} "
                    f"timeout={value['supervision_timeout_ms']}ms "
                    f"({hex_bytes(raw)})"
                ),
            }
        )
        return result
    if uuid == "00002a23-0000-1000-8000-00805f9b34fb" and len(raw) == 8:
        manufacturer = hex_bytes(raw[:5])
        oui = hex_bytes(raw[5:])
        result.update(
            {
                "type": "system_id",
                "value": {
                    "manufacturer_identifier_hex": manufacturer,
                    "organizationally_unique_identifier_hex": oui,
                },
                "display": f"manufacturer={manufacturer} oui={oui} ({hex_bytes(raw)})",
            }
        )
        return result
    if uuid == "00002a2a-0000-1000-8000-00805f9b34fb" and raw:
        text = raw[2:].decode("ascii", errors="replace") if len(raw) > 2 else ""
        result.update(
            {
                "type": "ieee_regulatory_certification",
                "value": {"list_type_hex": hex_bytes(raw[:2]), "text": text},
                "display": f"list_type={hex_bytes(raw[:2])} text={text!r} ({hex_bytes(raw)})",
            }
        )
        return result
    if uuid == "00002a50-0000-1000-8000-00805f9b34fb" and len(raw) >= 7:
        vendor_id_source = raw[0]
        vendor_id = _uint16_le(raw, 1)
        product_id = _uint16_le(raw, 3)
        product_version = _uint16_le(raw, 5)
        result.update(
            {
                "type": "pnp_id",
                "value": {
                    "vendor_id_source": vendor_id_source,
                    "vendor_id": vendor_id,
                    "product_id": product_id,
                    "product_version": product_version,
                },
                "display": (
                    "pnp_id="
                    f"source={vendor_id_source} vendor=0x{vendor_id:04X} "
                    f"product=0x{product_id:04X} version=0x{product_version:04X} "
                    f"({hex_bytes(raw)})"
                ),
            }
        )
        return result
    if uuid == "00002aa6-0000-1000-8000-00805f9b34fb" and raw:
        result.update(
            {
                "type": "boolean",
                "value": bool(raw[0]),
                "display": f"{bool(raw[0])} ({hex_bytes(raw)})",
            }
        )
        return result
    if uuid == "00002b3a-0000-1000-8000-00805f9b34fb" and raw:
        result.update({"type": "bitfield", "value": raw[0], "display": f"0x{raw[0]:02X} ({hex_bytes(raw)})"})
        return result
    if uuid == "00002a38-0000-1000-8000-00805f9b34fb" and raw:
        locations = {
            0: "Other",
            1: "Chest",
            2: "Wrist",
            3: "Finger",
            4: "Hand",
            5: "Ear Lobe",
            6: "Foot",
        }
        result.update(
            {
                "type": "body_sensor_location",
                "value": raw[0],
                "label": locations.get(raw[0]),
                "display": f"{raw[0]} {locations.get(raw[0], '<unknown>')} ({hex_bytes(raw)})",
            }
        )
        return result
    if uuid in PRIVATE_TABLE_CHARACTERISTICS:
        decoded = _decode_private_table(raw)
        if decoded is not None:
            result.update(decoded)
            return result
    if raw:
        result.update({"type": "bytes", "display": hex_bytes(raw)})
    else:
        result.update({"type": "bytes", "display": "<empty>"})
    return result


def _format_mac(raw: bytes) -> str:
    return ":".join(f"{byte:02X}" for byte in raw)


def _uint16_le(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def _uint32_le(raw: bytes, offset: int) -> int:
    return (
        raw[offset]
        | (raw[offset + 1] << 8)
        | (raw[offset + 2] << 16)
        | (raw[offset + 3] << 24)
    )


def _decode_private_table(raw: bytes) -> dict[str, Any] | None:
    if len(raw) >= 1 and (len(raw) - 1) % 6 == 0 and raw[0] == (len(raw) - 1) // 6:
        header = raw[:1]
        data = raw[1:]
        count = raw[0]
    elif len(raw) >= 2 and (len(raw) - 2) % 6 == 0 and raw[1] == (len(raw) - 2) // 6:
        header = raw[:2]
        data = raw[2:]
        count = raw[1]
    else:
        return None

    records = []
    for offset in range(0, len(data), 6):
        tag = _uint16_le(data, offset)
        value = _uint32_le(data, offset + 2)
        records.append(
            {
                "tag": tag,
                "tag_hex": f"0x{tag:04X}",
                "value": value,
                "value_hex": f"0x{value:08X}",
            }
        )

    display_records = ", ".join(f"{record['tag_hex']}={record['value_hex']}" for record in records)
    return {
        "type": "private_table",
        "value": {"header_hex": hex_bytes(header), "count": count, "records": records},
        "display": f"private_table header={hex_bytes(header)} count={count} records=[{display_records}]",
    }

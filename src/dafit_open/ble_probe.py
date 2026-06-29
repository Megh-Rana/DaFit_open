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
    CRP_WRITE_CMD_2,
    CRP_WRITE_PRIMARY,
    HEART_RATE_MEASUREMENT,
    Packet,
    QUERY_FILE_TRANSFER_PACKET_LENGTH,
    QUERY_DEVICE_VERSION,
    QUERY_DISPLAY_WATCH_FACE,
    QUERY_HISTORY_TRAINING_DETAIL,
    QUERY_SETS,
    QUERY_SUPPORT_WATCH_FACE,
    QUERY_WATCH_FACE_LIST,
    QUERY_WATCH_FACE_SCREEN,
    WATCH_FACE_SUPPORT_QUERY_PACKETS,
    decode_frame,
    file_transfer_abort_packet,
    file_transfer_check_packet,
    hex_bytes,
    parse_display_watch_face,
    parse_file_transfer_crc,
    parse_file_transfer_offset,
    parse_frame,
    parse_package_length,
    parse_store_watch_face_crc,
    parse_store_watch_face_offset,
    parse_support_watch_faces,
    parse_watch_face_list,
    parse_watch_face_screen,
    query_training_detail_packet,
    query_training_series_packet,
    set_display_time_packet,
    set_display_watch_face_packet,
    set_do_not_disturb_time_packet,
    set_goal_steps_packet,
    set_time_system_packet,
    store_watch_face_check_packet,
    store_watch_face_prepare_packet,
    watch_face_background_check_packet,
)
from .watchface_image import (
    crp_crc16,
    inspect_watch_face_package,
    plan_original_background_transfer,
    plan_watch_face_transfer,
    wrap_transfer_chunk,
)
from .watchface_store import (
    DEFAULT_STORE_PACKET_LENGTH,
    inspect_store_watch_face_bin,
    plan_store_watch_face_transfer,
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


async def watch_faces(
    address: str,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    wait_timeout: float = 3.0,
    extended: bool = False,
    json_out: str | None = None,
) -> None:
    capture = _new_capture(
        "watch-faces",
        address,
        {
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
            "wait_timeout": wait_timeout,
            "extended": extended,
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
            await _watch_faces_device(
                device,
                timeout,
                pair=pair,
                wait_timeout=wait_timeout,
                extended=extended,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"watch-faces failed: {type(exc).__name__}: {exc}")
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

    print("watch-faces failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def upload_watch_face_raw(
    address: str,
    package_dir: str,
    transfer_type: int = 14,
    packet_length: int | None = None,
    include_thumbnail: bool = True,
    name_mode: str = "path",
    max_chunks: int = 0,
    complete: bool = False,
    wait_timeout: float = 8.0,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 1,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    inspection = inspect_watch_face_package(package_dir)
    if not inspection["valid"]:
        raise ValueError(f"invalid watch-face package: {package_dir}")
    if packet_length is not None and packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    if max_chunks < 0:
        raise ValueError(f"max chunks must be non-negative: {max_chunks}")

    capture = _new_capture(
        "upload-watch-face",
        address,
        {
            "package_dir": package_dir,
            "transfer_type": transfer_type,
            "packet_length": packet_length,
            "include_thumbnail": include_thumbnail,
            "name_mode": name_mode,
            "max_chunks": max_chunks,
            "complete": complete,
            "wait_timeout": wait_timeout,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    capture["watch_face_package"] = inspection
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
            await _upload_watch_face_raw_device(
                device,
                package_dir,
                transfer_type,
                packet_length,
                include_thumbnail,
                name_mode,
                max_chunks,
                complete,
                wait_timeout,
                timeout,
                pair=pair,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"upload-watch-face failed: {type(exc).__name__}: {exc}")
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

    print("upload-watch-face failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def upload_store_watch_face(
    address: str,
    path: str,
    packet_length: int = DEFAULT_STORE_PACKET_LENGTH,
    max_chunks: int = 0,
    complete: bool = False,
    wait_timeout: float = 8.0,
    set_display: int | None = None,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 1,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    inspection = inspect_store_watch_face_bin(path)
    if packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    if max_chunks < 0:
        raise ValueError(f"max chunks must be non-negative: {max_chunks}")

    capture = _new_capture(
        "upload-watch-face-bin",
        address,
        {
            "path": path,
            "packet_length": packet_length,
            "max_chunks": max_chunks,
            "complete": complete,
            "wait_timeout": wait_timeout,
            "set_display": set_display,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    capture["store_watch_face_bin"] = inspection
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
            await _upload_store_watch_face_device(
                device,
                path,
                packet_length,
                max_chunks,
                complete,
                wait_timeout,
                set_display,
                timeout,
                pair=pair,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"upload-watch-face-bin failed: {type(exc).__name__}: {exc}")
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

    print("upload-watch-face-bin failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def upload_original_background(
    address: str,
    package_dir: str,
    packet_length: int | None = None,
    max_chunks: int = 0,
    complete: bool = False,
    wait_timeout: float = 8.0,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 1,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    plan = plan_original_background_transfer(
        package_dir,
        packet_length=packet_length or 64,
        chunk_preview_count=0,
    )
    if packet_length is not None and packet_length <= 0:
        raise ValueError(f"packet length out of range: {packet_length}")
    if max_chunks < 0:
        raise ValueError(f"max chunks must be non-negative: {max_chunks}")

    capture = _new_capture(
        "upload-original-background",
        address,
        {
            "package_dir": package_dir,
            "packet_length": packet_length,
            "max_chunks": max_chunks,
            "complete": complete,
            "wait_timeout": wait_timeout,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
        },
    )
    capture["original_background_plan"] = plan.to_dict()
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
            await _upload_original_background_device(
                device,
                package_dir,
                packet_length,
                max_chunks,
                complete,
                wait_timeout,
                timeout,
                pair=pair,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"upload-original-background failed: {type(exc).__name__}: {exc}")
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

    print("upload-original-background failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def set_settings(
    address: str,
    goal_steps: int | None = None,
    time_system: int | None = None,
    display_time: bool | None = None,
    dnd: tuple[int, int, int, int] | None = None,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    verify: bool = True,
    json_out: str | None = None,
) -> None:
    packets: list[tuple[str, Packet]] = []
    if goal_steps is not None:
        packets.append((f"goal steps={goal_steps}", set_goal_steps_packet(goal_steps)))
    if time_system is not None:
        packets.append((f"time system={time_system}", set_time_system_packet(time_system)))
    if display_time is not None:
        packets.append((f"display time enabled={display_time}", set_display_time_packet(display_time)))
    if dnd is not None:
        packets.append(
            (
                f"dnd={dnd[0]:02d}:{dnd[1]:02d}-{dnd[2]:02d}:{dnd[3]:02d}",
                set_do_not_disturb_time_packet(*dnd),
            )
        )
    if not packets:
        raise ValueError("at least one setting must be supplied")

    capture = _new_capture(
        "set-settings",
        address,
        {
            "goal_steps": goal_steps,
            "time_system": time_system,
            "display_time": display_time,
            "dnd": list(dnd) if dnd is not None else None,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
            "verify": verify,
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
            await _set_settings_device(
                device,
                packets,
                timeout,
                pair=pair,
                verify=verify,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"set-settings failed: {type(exc).__name__}: {exc}")
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

    print("set-settings failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def write_alarm_packets(
    address: str,
    operation: str,
    packets: list[tuple[str, Packet]],
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    verify: bool = True,
    json_out: str | None = None,
) -> None:
    if not packets:
        raise ValueError("at least one alarm packet must be supplied")

    capture = _new_capture(
        "alarm-write",
        address,
        {
            "operation": operation,
            "packet_count": len(packets),
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
            "verify": verify,
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
            await _write_alarm_packets_device(
                device,
                packets,
                timeout,
                pair=pair,
                verify=verify,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"alarm-write failed: {type(exc).__name__}: {exc}")
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

    print("alarm-write failed after all retries")
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


async def training_series(
    address: str,
    training_id: int,
    kinds: list[str],
    offset: int = 0,
    chunk_timeout: float = 6.0,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    json_out: str | None = None,
) -> None:
    if not 0 <= training_id <= 0xFF:
        raise ValueError(f"training id must be between 0 and 255: {training_id}")
    if not 0 <= offset <= 0xFFFF:
        raise ValueError(f"training series offset must be between 0 and 65535: {offset}")
    if "all" in kinds:
        kinds = ["heart-rate", "steps", "distance"]

    capture = _new_capture(
        "training-series",
        address,
        {
            "training_id": training_id,
            "kinds": kinds,
            "offset": offset,
            "chunk_timeout": chunk_timeout,
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
            await _training_series_device(
                device,
                training_id,
                kinds,
                offset,
                chunk_timeout,
                timeout,
                pair=pair,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"training-series failed: {type(exc).__name__}: {exc}")
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

    print("training-series failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")
    _write_capture(json_out, capture)


async def sync_training(
    address: str,
    kinds: list[str],
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 3,
    pair: bool = False,
    direct: bool = False,
    chunk_timeout: float = 6.0,
    json_out: str | None = None,
) -> None:
    if "all" in kinds:
        kinds = ["heart-rate", "steps", "distance"]

    capture = _new_capture(
        "sync-training",
        address,
        {
            "kinds": kinds,
            "timeout": timeout,
            "scan_timeout": scan_timeout,
            "retries": retries,
            "pair": pair,
            "direct": direct,
            "chunk_timeout": chunk_timeout,
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
            await _sync_training_device(
                device,
                kinds,
                timeout,
                pair=pair,
                chunk_timeout=chunk_timeout,
                capture=capture,
            )
            _write_capture(json_out, capture)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
            capture["errors"].append({"attempt": attempt, "type": "TimeoutError", "message": str(exc)})
        except Exception as exc:
            last_error = exc
            print(f"sync-training failed: {type(exc).__name__}: {exc}")
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

    print("sync-training failed after all retries")
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


async def _watch_faces_device(
    device: BLEDevice | str,
    timeout: float,
    pair: bool,
    wait_timeout: float,
    extended: bool,
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
        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; cannot query watch faces")
            return

        capture["watch_faces"] = {
            "device_version": None,
            "display_slot": None,
            "slots": [],
            "support": None,
            "screen": None,
            "unanswered": [],
        }
        mtu_payload = _guess_mtu_payload(client)
        await _query_watch_face_state(
            client,
            write_char,
            write_with_response,
            mtu_payload,
            wait_timeout,
            extended,
            notification_queue,
            capture,
        )

        for char in notify_chars:
            await client.stop_notify(char)


async def _upload_watch_face_raw_device(
    device: BLEDevice | str,
    package_dir: str,
    transfer_type: int,
    packet_length: int | None,
    include_thumbnail: bool,
    name_mode: str,
    max_chunks: int,
    complete: bool,
    wait_timeout: float,
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    plan = plan_watch_face_transfer(
        package_dir,
        transfer_type=transfer_type,
        include_thumbnail=include_thumbnail,
        packet_length=packet_length,
        chunk_preview_count=0,
        name_mode=name_mode,
    )
    capture["watch_face_transfer_plan"] = plan.to_dict()
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        command_char = None
        command_with_response = True
        transfer_char = None
        transfer_with_response = False
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    command_char = char
                    command_with_response = "write" in char.properties
                if uuid == CRP_WRITE_CMD_2 and _can_write(char.properties):
                    transfer_char = char
                    transfer_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)
        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        try:
            if command_char is None:
                print("no primary write characteristic found; cannot upload watch face")
                return
            if transfer_char is None:
                print("no transfer write characteristic found; cannot upload watch face")
                return

            gatt_payload = _guess_mtu_payload(client)
            negotiated = packet_length
            if negotiated is None:
                print("negotiating file packet length with cmd=0xBA")
                await _write_packet_fragmented(
                    client,
                    command_char,
                    QUERY_FILE_TRANSFER_PACKET_LENGTH,
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
                negotiated = await _wait_for_package_length(notification_queue, wait_timeout)
                if negotiated is None:
                    negotiated = 64
                    print(f"no package-length response within {wait_timeout:.1f}s; falling back to {negotiated}")
                else:
                    print(f"negotiated file packet length: {negotiated}")
            capture["watch_face_upload"] = {
                "packet_length": negotiated,
                "gatt_payload": gatt_payload,
                "complete_requested": complete,
                "max_chunks": max_chunks,
                "files": [],
            }

            print("sending watch-face transfer prepare packet")
            await _write_packet_fragmented(
                client,
                command_char,
                plan.prepare_packet,
                command_with_response,
                gatt_payload,
                capture,
                channel="command",
            )
            await asyncio.sleep(0.5)

            for filename, start_packet in plan.start_packets:
                file_path = Path(package_dir) / filename
                file_data = file_path.read_bytes()
                file_record = {
                    "file": filename,
                    "size": len(file_data),
                    "crc16": f"0x{crp_crc16(file_data):04X}",
                    "chunks_sent": 0,
                    "events": [],
                    "completed": False,
                    "aborted": False,
                }
                capture["watch_face_upload"]["files"].append(file_record)
                print(f"starting file transfer: {filename} ({len(file_data)} bytes)")
                await _write_packet_fragmented(
                    client,
                    command_char,
                    start_packet,
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
                completed = await _transfer_watch_face_file(
                    client,
                    command_char,
                    command_with_response,
                    transfer_char,
                    transfer_with_response,
                    file_data,
                    negotiated,
                    gatt_payload,
                    wait_timeout,
                    complete,
                    max_chunks,
                    notification_queue,
                    capture,
                    file_record,
                )
                if not completed:
                    print("stopping remaining files after incomplete transfer")
                    break
        finally:
            for char in notify_chars:
                await client.stop_notify(char)


async def _upload_store_watch_face_device(
    device: BLEDevice | str,
    path: str,
    packet_length: int,
    max_chunks: int,
    complete: bool,
    wait_timeout: float,
    set_display: int | None,
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    file_data = Path(path).read_bytes()
    plan = plan_store_watch_face_transfer(path, packet_length=packet_length, chunk_preview_count=0)
    capture["store_watch_face_transfer_plan"] = plan.to_dict()
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        command_char = None
        command_with_response = True
        transfer_char = None
        transfer_with_response = False
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    command_char = char
                    command_with_response = "write" in char.properties
                if uuid == CRP_WRITE_CMD_2 and _can_write(char.properties):
                    transfer_char = char
                    transfer_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)
        gatt_payload = await _negotiate_large_write_payload(
            client,
            capture,
            required_payload=packet_length,
        )
        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        try:
            if command_char is None:
                print("no primary write characteristic found; cannot upload watch-face bin")
                return
            if transfer_char is None:
                print("no transfer write characteristic found; cannot upload watch-face bin")
                return

            capture["store_watch_face_upload"] = {
                "packet_length": packet_length,
                "gatt_payload": gatt_payload,
                "large_write_ready": gatt_payload >= packet_length,
                "complete_requested": complete,
                "max_chunks": max_chunks,
                "chunks_sent": 0,
                "events": [],
                "completed": False,
                "display_set": None,
            }
            if (complete or max_chunks > 0) and gatt_payload < packet_length:
                print(
                    "store watch-face upload needs a single-write payload of "
                    f"{packet_length} bytes, but negotiated payload is {gatt_payload}; "
                    "stopping before transfer"
                )
                capture["store_watch_face_upload"]["error"] = "mtu_payload_too_small"
                return

            print(f"sending store watch-face prepare size={len(file_data)}")
            await _write_packet_fragmented(
                client,
                command_char,
                store_watch_face_prepare_packet(len(file_data)),
                command_with_response,
                gatt_payload,
                capture,
                channel="command",
            )
            await asyncio.sleep(0.15)

            handshake_packets = (
                Packet(0xB6, bytes([0x00, 0x01])),
                Packet(0xB6, bytes([0x01, 0x01])),
                Packet(0xBC, bytes([0x01, 0x00])),
                Packet(0x34, bytes([0x00])),
            )
            for packet in handshake_packets:
                await _write_packet_fragmented(
                    client,
                    command_char,
                    packet,
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
                await asyncio.sleep(0.15)

            completed = await _transfer_store_watch_face_bin(
                client,
                command_char,
                command_with_response,
                transfer_char,
                transfer_with_response,
                file_data,
                packet_length,
                gatt_payload,
                wait_timeout,
                complete,
                max_chunks,
                notification_queue,
                capture,
                capture["store_watch_face_upload"],
            )
            if completed and set_display is not None:
                print(f"setting display watch-face slot after upload: {set_display}")
                await _write_packet_fragmented(
                    client,
                    command_char,
                    set_display_watch_face_packet(set_display),
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
                capture["store_watch_face_upload"]["display_set"] = set_display
                await asyncio.sleep(0.5)
        finally:
            for char in notify_chars:
                await client.stop_notify(char)


async def _upload_original_background_device(
    device: BLEDevice | str,
    package_dir: str,
    packet_length: int | None,
    max_chunks: int,
    complete: bool,
    wait_timeout: float,
    timeout: float,
    pair: bool,
    capture: dict[str, Any],
) -> None:
    package_path = Path(package_dir)
    file_data = (package_path / "background.rgb565").read_bytes()
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")
        capture["connected"] = client.is_connected

        services = client.services
        command_char = None
        command_with_response = True
        transfer_char = None
        transfer_with_response = False
        notify_chars = []

        for service in services:
            print(f"service {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  char {char.uuid} [{props}]")
                uuid = char.uuid.lower()
                if uuid == CRP_WRITE_PRIMARY and _can_write(char.properties):
                    command_char = char
                    command_with_response = "write" in char.properties
                if uuid == CRP_WRITE_CMD_2 and _can_write(char.properties):
                    transfer_char = char
                    transfer_with_response = "write" in char.properties
                if uuid in NOTIFY_UUIDS and "notify" in char.properties:
                    notify_chars.append(char)

        capture["services"] = _services_snapshot(services)
        gatt_payload = await _negotiate_large_write_payload(
            client,
            capture,
            required_payload=max(packet_length or 64, 64) + 5,
        )
        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        try:
            if command_char is None:
                print("no primary write characteristic found; cannot upload original background")
                return
            if transfer_char is None:
                print("no transfer write characteristic found; cannot upload original background")
                return

            negotiated = packet_length
            plan = plan_original_background_transfer(
                package_dir,
                packet_length=negotiated or 64,
                chunk_preview_count=0,
            )
            capture["original_background_transfer"] = {
                "packet_length": negotiated,
                "gatt_payload": gatt_payload,
                "complete_requested": complete,
                "max_chunks": max_chunks,
                "chunks_sent": 0,
                "events": [],
                "completed": False,
            }

            print(f"sending original background size={len(file_data)}")
            await _write_packet_fragmented(
                client,
                command_char,
                plan.size_packet,
                command_with_response,
                gatt_payload,
                capture,
                channel="command",
            )
            await asyncio.sleep(0.2)

            if negotiated is None:
                print("negotiating file packet length with cmd=0xBA")
                await _write_packet_fragmented(
                    client,
                    command_char,
                    QUERY_FILE_TRANSFER_PACKET_LENGTH,
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
                negotiated = await _wait_for_package_length(notification_queue, wait_timeout)
                if negotiated is None:
                    negotiated = 64
                    print(f"no package-length response within {wait_timeout:.1f}s; falling back to {negotiated}")
                else:
                    print(f"negotiated file packet length: {negotiated}")
                plan = plan_original_background_transfer(
                    package_dir,
                    packet_length=negotiated,
                    chunk_preview_count=0,
                )
                capture["original_background_plan"] = plan.to_dict()
                capture["original_background_transfer"]["packet_length"] = negotiated

            completed = await _transfer_original_background(
                client,
                command_char,
                command_with_response,
                transfer_char,
                transfer_with_response,
                file_data,
                negotiated,
                gatt_payload,
                wait_timeout,
                complete,
                max_chunks,
                notification_queue,
                capture,
                capture["original_background_transfer"],
            )
            capture["original_background_transfer"]["completed"] = completed
        finally:
            for char in notify_chars:
                await client.stop_notify(char)


async def _set_settings_device(
    device: BLEDevice | str,
    packets: list[tuple[str, Packet]],
    timeout: float,
    pair: bool,
    verify: bool,
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
            print("no primary write characteristic found; cannot set settings")
            return

        mtu_payload = _guess_mtu_payload(client)
        for label, packet in packets:
            print(f"setting {label}")
            await _write_packet(
                client,
                write_char,
                packet,
                write_with_response,
                mtu_payload,
                capture,
            )
            await asyncio.sleep(0.5)

        if verify:
            print("verifying settings with settings-basic query")
            await _send_queries(
                client,
                write_char,
                write_with_response=write_with_response,
                mtu_payload=mtu_payload,
                query_set="settings-basic",
                capture=capture,
            )
            await asyncio.sleep(3)
        else:
            await asyncio.sleep(2)

        for char in notify_chars:
            await client.stop_notify(char)


async def _write_alarm_packets_device(
    device: BLEDevice | str,
    packets: list[tuple[str, Packet]],
    timeout: float,
    pair: bool,
    verify: bool,
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
            print("no primary write characteristic found; cannot write alarms")
            return

        mtu_payload = _guess_mtu_payload(client)
        for label, packet in packets:
            print(f"alarm write {label}")
            await _write_packet(
                client,
                write_char,
                packet,
                write_with_response,
                mtu_payload,
                capture,
            )
            await asyncio.sleep(0.5)

        if verify:
            print("verifying alarms with alarms query")
            await _send_queries(
                client,
                write_char,
                write_with_response=write_with_response,
                mtu_payload=mtu_payload,
                query_set="alarms",
                capture=capture,
            )
            await asyncio.sleep(3)
        else:
            await asyncio.sleep(2)

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


async def _training_series_device(
    device: BLEDevice | str,
    training_id: int,
    kinds: list[str],
    offset: int,
    chunk_timeout: float,
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

        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; cannot query training series")
            return

        mtu_payload = _guess_mtu_payload(client)
        for kind in kinds:
            await _query_training_series_kind(
                client,
                write_char,
                write_with_response,
                mtu_payload,
                training_id,
                kind,
                offset,
                chunk_timeout,
                notification_queue,
                capture,
            )

        for char in notify_chars:
            await client.stop_notify(char)


async def _sync_training_device(
    device: BLEDevice | str,
    kinds: list[str],
    timeout: float,
    pair: bool,
    chunk_timeout: float,
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
        notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

        for char in notify_chars:
            await client.start_notify(char, _make_notification_handler(capture, notification_queue))
            print(f"notify enabled: {char.uuid}")
            capture["notifications_enabled"].append(_char_snapshot(char))

        if write_char is None:
            print("no primary write characteristic found; cannot sync training")
            return

        mtu_payload = _guess_mtu_payload(client)
        print("querying training list")
        await _write_packet(
            client,
            write_char,
            QUERY_HISTORY_TRAINING_DETAIL,
            write_with_response,
            mtu_payload,
            capture,
        )
        training_ids = await _wait_for_training_list_response(notification_queue, chunk_timeout)
        if not training_ids:
            print(f"no training list response within {chunk_timeout:.1f}s")
            return
        print(f"training ids: {training_ids}")

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
            detail_ok = await _wait_for_training_detail_response(
                notification_queue,
                training_id,
                chunk_timeout,
            )
            if not detail_ok:
                print(f"no detail response for id={training_id} within {chunk_timeout:.1f}s")
                continue
            for kind in kinds:
                await _query_training_series_kind(
                    client,
                    write_char,
                    write_with_response,
                    mtu_payload,
                    training_id,
                    kind,
                    0,
                    chunk_timeout,
                    notification_queue,
                    capture,
                )

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


def _make_notification_handler(
    capture: dict[str, Any],
    queue: asyncio.Queue[bytes] | None = None,
):
    def handler(sender: object, data: bytearray) -> None:
        _handle_notification(sender, data, capture=capture)
        if queue is not None:
            queue.put_nowait(bytes(data))

    return handler


async def _query_watch_face_state(
    client: BleakClient,
    write_char: object,
    write_with_response: bool,
    mtu_payload: int,
    wait_timeout: float,
    extended: bool,
    notification_queue: asyncio.Queue[bytes],
    capture: dict[str, Any],
) -> None:
    queries = [
        ("device version", QUERY_DEVICE_VERSION, 0x2E),
        ("current display slot", QUERY_DISPLAY_WATCH_FACE, 0x29),
        ("installed watch-face slots", QUERY_WATCH_FACE_LIST, 0xA6),
        ("watch-face support", QUERY_SUPPORT_WATCH_FACE, 0x84),
        ("watch-face screen", QUERY_WATCH_FACE_SCREEN, 0xB4),
    ]
    if extended:
        queries.extend(
            [
                (f"extended watch-face 0xB4 {packet.payload[0]:02X}", packet, 0xB4)
                for packet in WATCH_FACE_SUPPORT_QUERY_PACKETS
                if packet.command == 0xB4
                and packet.payload
                and packet.payload != QUERY_WATCH_FACE_SCREEN.payload
            ]
        )

    for label, packet, response_command in queries:
        print(f"querying {label}")
        await _write_packet(
            client,
            write_char,
            packet,
            write_with_response,
            mtu_payload,
            capture,
        )
        frame = await _wait_for_command_response(
            notification_queue,
            response_command,
            wait_timeout,
            predicate=_watch_face_response_predicate(packet),
        )
        if frame is None:
            print(f"no {label} response within {wait_timeout:.1f}s")
            capture["watch_faces"]["unanswered"].append(
                {"command": packet.command, "payload_hex": hex_bytes(packet.payload), "label": label}
            )
            continue
        _merge_watch_face_response(capture["watch_faces"], frame)

    _print_watch_face_summary(capture["watch_faces"])


def _watch_face_response_predicate(packet: Packet):
    if packet.command != 0xB4:
        return None
    if not packet.payload:
        return None
    expected_subcommand = packet.payload[0]

    def predicate(frame) -> bool:
        return bool(frame.payload and frame.payload[0] == expected_subcommand)

    return predicate


def _merge_watch_face_response(summary: dict[str, Any], frame) -> None:
    if frame.command == 0x29:
        summary["display_slot"] = parse_display_watch_face(frame.payload)
    elif frame.command == 0xA6:
        slots = parse_watch_face_list(frame.payload)
        if slots is not None:
            summary["slots"] = [slot.to_dict() for slot in slots]
    elif frame.command == 0x84:
        support = parse_support_watch_faces(frame.payload)
        if support is not None:
            summary["support"] = support.to_dict()
    elif frame.command == 0xB4:
        screen = parse_watch_face_screen(frame.payload)
        if screen is not None:
            summary["screen"] = screen.to_dict()
    elif frame.command == 0x2E and frame.payload:
        summary["device_version"] = frame.payload[0]


def _print_watch_face_summary(summary: dict[str, Any]) -> None:
    print("watch-face summary:")
    print(f"  current slot: {_display_value(summary.get('display_slot'))}")
    slots = summary.get("slots") or []
    if slots:
        print("  installed slots:")
        for slot in slots:
            marker = "*" if slot.get("index") == summary.get("display_slot") else " "
            print(
                f"  {marker} index={slot.get('index')} "
                f"type={slot.get('kind')} id={slot.get('watch_face_id')}"
            )
    else:
        print("  installed slots: <none>")
    print(f"  support: {_display_value(summary.get('support'))}")
    print(f"  screen: {_display_value(summary.get('screen'))}")
    unanswered = summary.get("unanswered") or []
    if unanswered:
        print(f"  unanswered probes: {len(unanswered)}")


def _display_value(value: object | None) -> str:
    if value is None:
        return "<unknown>"
    return str(value)


async def _query_training_series_kind(
    client: BleakClient,
    write_char: object,
    write_with_response: bool,
    mtu_payload: int,
    training_id: int,
    kind: str,
    offset: int,
    chunk_timeout: float,
    notification_queue: asyncio.Queue[bytes],
    capture: dict[str, Any],
) -> None:
    response_subcommands = {
        "heart-rate": 0x05,
        "steps": 0x08,
        "distance": 0x0A,
    }
    response_subcommand = response_subcommands[kind]
    current_offset = offset
    seen_offsets: set[int] = set()

    while True:
        if current_offset in seen_offsets:
            print(f"stopping {kind}: repeated offset {current_offset}")
            return
        seen_offsets.add(current_offset)

        print(f"querying training {kind} id={training_id} offset={current_offset}")
        await _write_packet(
            client,
            write_char,
            query_training_series_packet(training_id, kind, current_offset),
            write_with_response,
            mtu_payload,
            capture,
        )

        next_offset = await _wait_for_training_series_response(
            notification_queue,
            training_id,
            response_subcommand,
            chunk_timeout,
        )
        if next_offset is None:
            print(f"no {kind} chunk response within {chunk_timeout:.1f}s")
            return
        if next_offset == 0xFFFF:
            print(f"training {kind} complete")
            return
        current_offset = next_offset


async def _wait_for_training_series_response(
    notification_queue: asyncio.Queue[bytes],
    training_id: int,
    response_subcommand: int,
    timeout: float,
) -> int | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != 0xB2 or len(frame.payload) < 4:
            continue
        if frame.payload[0] != response_subcommand or frame.payload[1] != training_id:
            continue
        return int.from_bytes(frame.payload[2:4], "big")


async def _wait_for_command_response(
    notification_queue: asyncio.Queue[bytes],
    command: int,
    timeout: float,
    predicate=None,
):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != command:
            continue
        if predicate is not None and not predicate(frame):
            continue
        return frame


async def _wait_for_training_list_response(
    notification_queue: asyncio.Queue[bytes],
    timeout: float,
) -> list[int] | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != 0xB2 or not frame.payload:
            continue
        if frame.payload[0] != 0x01:
            continue
        return _training_ids_from_list_payload(frame.payload)


async def _wait_for_training_detail_response(
    notification_queue: asyncio.Queue[bytes],
    training_id: int,
    timeout: float,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return False
        frame = parse_frame(raw)
        if frame is None or frame.command != 0xB2 or len(frame.payload) < 2:
            continue
        if frame.payload[0] == 0x03 and frame.payload[1] == training_id:
            return True


def _training_ids_from_list_payload(payload: bytes) -> list[int]:
    if len(payload) % 5 != 1:
        return []
    training_ids = []
    for offset in range(1, len(payload), 5):
        timestamp = int.from_bytes(payload[offset : offset + 4], "little")
        if timestamp > 1:
            training_ids.append(offset // 5)
    return training_ids


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


async def _transfer_watch_face_file(
    client: BleakClient,
    command_char: object,
    command_with_response: bool,
    transfer_char: object,
    transfer_with_response: bool,
    file_data: bytes,
    packet_length: int,
    gatt_payload: int,
    wait_timeout: float,
    complete: bool,
    max_chunks: int,
    notification_queue: asyncio.Queue[bytes],
    capture: dict[str, Any],
    file_record: dict[str, Any],
) -> bool:
    chunks_sent = 0
    while True:
        event = await _wait_for_transfer_event(notification_queue, wait_timeout)
        if event is None:
            print(f"no file-transfer event within {wait_timeout:.1f}s; sending abort")
            await _send_transfer_abort(
                client,
                command_char,
                command_with_response,
                gatt_payload,
                capture,
                file_record,
            )
            return False
        file_record["events"].append(event)
        if event["type"] == "offset":
            offset = int(event["offset"])
            if offset >= len(file_data):
                print(f"watch requested offset beyond file size: {offset}")
                await _send_transfer_abort(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    file_record,
                )
                return False
            if not complete and chunks_sent >= max_chunks:
                print(f"chunk limit reached ({max_chunks}); sending abort")
                await _send_transfer_abort(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    file_record,
                )
                return False
            chunk = file_data[offset : offset + packet_length]
            frame = wrap_transfer_chunk(chunk, packet_length)
            print(
                f"sending file chunk offset={offset} data_len={len(chunk)} "
                f"crc=0x{crp_crc16(chunk):04X}"
            )
            await _write_raw_fragmented(
                client,
                transfer_char,
                frame,
                transfer_with_response,
                gatt_payload,
                capture,
                channel="transfer",
                packet_command=0xB7,
            )
            chunks_sent += 1
            file_record["chunks_sent"] = chunks_sent
            continue
        if event["type"] == "crc":
            expected = crp_crc16(file_data)
            received = event.get("crc16")
            ok = received == expected
            print(
                f"file transfer CRC received={_format_optional_crc(received)} "
                f"expected=0x{expected:04X} ok={ok}"
            )
            await _write_packet_fragmented(
                client,
                command_char,
                file_transfer_check_packet(ok),
                command_with_response,
                gatt_payload,
                capture,
                channel="command",
            )
            file_record["completed"] = ok
            return ok
        print(f"unhandled file-transfer event: {event}")


async def _transfer_store_watch_face_bin(
    client: BleakClient,
    command_char: object,
    command_with_response: bool,
    transfer_char: object,
    transfer_with_response: bool,
    file_data: bytes,
    packet_length: int,
    gatt_payload: int,
    wait_timeout: float,
    complete: bool,
    max_chunks: int,
    notification_queue: asyncio.Queue[bytes],
    capture: dict[str, Any],
    upload_record: dict[str, Any],
) -> bool:
    chunks_sent = 0
    while True:
        event = await _wait_for_store_watch_face_event(notification_queue, wait_timeout)
        if event is None:
            print(f"no store watch-face event within {wait_timeout:.1f}s")
            return False
        upload_record["events"].append(event)
        if event["type"] == "offset":
            index = int(event["index"])
            offset = index * packet_length
            if offset >= len(file_data):
                print(f"watch requested chunk index beyond file size: {index}")
                return False
            if not complete and chunks_sent >= max_chunks:
                print(f"chunk limit reached ({max_chunks}); stopping without success check")
                return False
            chunk = file_data[offset : offset + packet_length]
            print(
                f"sending store watch-face chunk index={index} offset={offset} "
                f"data_len={len(chunk)} crc=0x{crp_crc16(chunk):04X}"
            )
            if len(chunk) > gatt_payload:
                print(
                    f"cannot send store watch-face chunk of {len(chunk)} bytes "
                    f"with negotiated payload {gatt_payload}; stopping"
                )
                upload_record["error"] = "chunk_exceeds_mtu_payload"
                return False
            await _write_raw_fragmented(
                client,
                transfer_char,
                chunk,
                transfer_with_response,
                gatt_payload,
                capture,
                channel="store-transfer",
                packet_command=0x74,
                allow_fragmented=False,
            )
            chunks_sent += 1
            upload_record["chunks_sent"] = chunks_sent
            continue
        if event["type"] == "crc":
            expected = crp_crc16(file_data)
            received = event.get("crc16")
            ok = received == expected
            print(
                f"store watch-face CRC received={_format_optional_crc(received)} "
                f"expected=0x{expected:04X} ok={ok}"
            )
            if ok:
                await _write_packet_fragmented(
                    client,
                    command_char,
                    store_watch_face_check_packet(True),
                    command_with_response,
                    gatt_payload,
                    capture,
                    channel="command",
                )
            upload_record["completed"] = ok
            return ok
        print(f"unhandled store watch-face event: {event}")


async def _transfer_original_background(
    client: BleakClient,
    command_char: object,
    command_with_response: bool,
    transfer_char: object,
    transfer_with_response: bool,
    file_data: bytes,
    packet_length: int,
    gatt_payload: int,
    wait_timeout: float,
    complete: bool,
    max_chunks: int,
    notification_queue: asyncio.Queue[bytes],
    capture: dict[str, Any],
    upload_record: dict[str, Any],
) -> bool:
    chunks_sent = 0
    while True:
        event = await _wait_for_original_background_event(notification_queue, wait_timeout)
        if event is None:
            print(f"no original background event within {wait_timeout:.1f}s")
            return False
        upload_record["events"].append(event)
        if event["type"] == "offset":
            offset = int(event["offset"])
            if offset >= len(file_data):
                print(f"watch requested offset beyond background size: {offset}")
                await _send_original_background_check(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    ok=False,
                )
                return False
            if not complete and chunks_sent >= max_chunks:
                print(f"chunk limit reached ({max_chunks}); sending failed background check")
                await _send_original_background_check(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    ok=False,
                )
                upload_record["aborted"] = True
                return False
            chunk = file_data[offset : offset + packet_length]
            frame = wrap_transfer_chunk(chunk, packet_length)
            print(
                f"sending original background chunk offset={offset} data_len={len(chunk)} "
                f"crc=0x{crp_crc16(chunk):04X}"
            )
            await _write_raw_fragmented(
                client,
                transfer_char,
                frame,
                transfer_with_response,
                gatt_payload,
                capture,
                channel="original-background-transfer",
                packet_command=0x6E,
            )
            chunks_sent += 1
            upload_record["chunks_sent"] = chunks_sent
            continue
        if event["type"] == "index":
            index = int(event["index"])
            offset = index * packet_length
            event["derived_offset"] = offset
            if offset >= len(file_data):
                print(f"watch requested chunk index beyond background size: {index}")
                await _send_original_background_check(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    ok=False,
                )
                return False
            if not complete and chunks_sent >= max_chunks:
                print(f"chunk limit reached ({max_chunks}); sending failed background check")
                await _send_original_background_check(
                    client,
                    command_char,
                    command_with_response,
                    gatt_payload,
                    capture,
                    ok=False,
                )
                upload_record["aborted"] = True
                return False
            chunk = file_data[offset : offset + packet_length]
            frame = wrap_transfer_chunk(chunk, packet_length)
            print(
                f"sending original background chunk index={index} offset={offset} "
                f"data_len={len(chunk)} crc=0x{crp_crc16(chunk):04X}"
            )
            await _write_raw_fragmented(
                client,
                transfer_char,
                frame,
                transfer_with_response,
                gatt_payload,
                capture,
                channel="original-background-transfer",
                packet_command=0x6E,
            )
            chunks_sent += 1
            upload_record["chunks_sent"] = chunks_sent
            continue
        if event["type"] == "crc":
            expected = crp_crc16(file_data)
            received = event.get("crc16")
            ok = received == expected
            print(
                f"original background CRC received={_format_optional_crc(received)} "
                f"expected=0x{expected:04X} ok={ok}"
            )
            await _send_original_background_check(
                client,
                command_char,
                command_with_response,
                gatt_payload,
                capture,
                ok=ok,
            )
            return ok
        print(f"unhandled original background event: {event}")


async def _send_transfer_abort(
    client: BleakClient,
    command_char: object,
    command_with_response: bool,
    gatt_payload: int,
    capture: dict[str, Any],
    file_record: dict[str, Any],
) -> None:
    await _write_packet_fragmented(
        client,
        command_char,
        file_transfer_abort_packet(),
        command_with_response,
        gatt_payload,
        capture,
        channel="command",
    )
    file_record["aborted"] = True


async def _send_original_background_check(
    client: BleakClient,
    command_char: object,
    command_with_response: bool,
    gatt_payload: int,
    capture: dict[str, Any],
    ok: bool,
) -> None:
    await _write_packet_fragmented(
        client,
        command_char,
        watch_face_background_check_packet(ok),
        command_with_response,
        gatt_payload,
        capture,
        channel="command",
    )


async def _wait_for_package_length(
    notification_queue: asyncio.Queue[bytes],
    timeout: float,
) -> int | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != 0xBA:
            continue
        packet_length = parse_package_length(frame.payload)
        if packet_length is not None:
            return packet_length


async def _wait_for_transfer_event(
    notification_queue: asyncio.Queue[bytes],
    timeout: float,
) -> dict[str, Any] | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != 0xB7:
            continue
        offset = parse_file_transfer_offset(frame.payload)
        if offset is not None:
            return {"type": "offset", "offset": offset, "payload_hex": hex_bytes(frame.payload)}
        crc = parse_file_transfer_crc(frame.payload)
        if crc is not None:
            return {"type": "crc", "crc16": crc, "payload_hex": hex_bytes(frame.payload)}
        return {"type": "other", "payload_hex": hex_bytes(frame.payload)}


async def _wait_for_store_watch_face_event(
    notification_queue: asyncio.Queue[bytes],
    timeout: float,
) -> dict[str, Any] | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command != 0x74:
            continue
        offset = parse_store_watch_face_offset(frame.payload)
        if offset is not None:
            return {"type": "offset", "index": offset, "payload_hex": hex_bytes(frame.payload)}
        crc = parse_store_watch_face_crc(frame.payload)
        if crc is not None:
            return {"type": "crc", "crc16": crc, "payload_hex": hex_bytes(frame.payload)}
        return {"type": "other", "payload_hex": hex_bytes(frame.payload)}


async def _wait_for_original_background_event(
    notification_queue: asyncio.Queue[bytes],
    timeout: float,
) -> dict[str, Any] | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            raw = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
        except TimeoutError:
            return None
        frame = parse_frame(raw)
        if frame is None or frame.command not in {0x6E, 0xB7, 0x74}:
            continue
        offset = parse_file_transfer_offset(frame.payload)
        if offset is not None:
            return {
                "type": "offset",
                "command": frame.command,
                "offset": offset,
                "payload_hex": hex_bytes(frame.payload),
            }
        crc = parse_file_transfer_crc(frame.payload)
        if crc is not None:
            return {
                "type": "crc",
                "command": frame.command,
                "crc16": crc,
                "payload_hex": hex_bytes(frame.payload),
            }
        index = parse_store_watch_face_offset(frame.payload)
        if index is not None:
            return {
                "type": "index",
                "command": frame.command,
                "index": index,
                "payload_hex": hex_bytes(frame.payload),
            }
        store_crc = parse_store_watch_face_crc(frame.payload)
        if store_crc is not None:
            return {
                "type": "crc",
                "command": frame.command,
                "crc16": store_crc,
                "payload_hex": hex_bytes(frame.payload),
            }
        return {
            "type": "other",
            "command": frame.command,
            "payload_hex": hex_bytes(frame.payload),
        }


async def _write_packet_fragmented(
    client: BleakClient,
    write_char: object,
    packet: Packet,
    write_with_response: bool,
    gatt_payload: int,
    capture: dict[str, Any],
    channel: str,
) -> None:
    data = packet.__class__(packet.command, packet.payload, gatt_payload).build()
    print(f">> {channel} cmd=0x{packet.command:02X}: {hex_bytes(data)}")
    capture["sent_packets"].append(
        {
            "timestamp": _utc_now(),
            "channel": channel,
            "command": packet.command,
            "payload_hex": hex_bytes(packet.payload),
            "hex": hex_bytes(data),
            "write_characteristic": _char_snapshot(write_char),
            "response": write_with_response,
            "fragmented": len(data) > gatt_payload,
        }
    )
    await _write_raw_fragmented(
        client,
        write_char,
        data,
        write_with_response,
        gatt_payload,
        capture,
        channel=channel,
        packet_command=packet.command,
    )


async def _write_raw_fragmented(
    client: BleakClient,
    write_char: object,
    data: bytes,
    write_with_response: bool,
    gatt_payload: int,
    capture: dict[str, Any],
    channel: str,
    packet_command: int | None,
    allow_fragmented: bool = True,
) -> None:
    if gatt_payload <= 0:
        raise ValueError(f"gatt payload out of range: {gatt_payload}")
    if len(data) > gatt_payload and not allow_fragmented:
        raise ValueError(
            f"{channel} write length {len(data)} exceeds GATT payload {gatt_payload}"
        )
    fragments = []
    for offset in range(0, len(data), gatt_payload):
        fragment = data[offset : offset + gatt_payload]
        fragments.append(
            {
                "offset": offset,
                "hex": hex_bytes(fragment),
                "length": len(fragment),
            }
        )
        await client.write_gatt_char(write_char, fragment, response=write_with_response)
        await asyncio.sleep(0.02)
    capture.setdefault("sent_fragments", []).append(
        {
            "timestamp": _utc_now(),
            "channel": channel,
            "command": packet_command,
            "total_length": len(data),
            "gatt_payload": gatt_payload,
            "fragment_count": len(fragments),
            "write_characteristic": _char_snapshot(write_char),
            "response": write_with_response,
            "fragments": fragments,
        }
    )


def _format_optional_crc(value: Any) -> str:
    if value is None:
        return "<none>"
    return f"0x{int(value):04X}"


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


async def _negotiate_large_write_payload(
    client: BleakClient,
    capture: dict[str, Any],
    required_payload: int,
) -> int:
    record: dict[str, Any] = {
        "required_payload": required_payload,
        "attempted": False,
        "ok": False,
        "mtu_size": None,
        "payload": 20,
    }
    backend = getattr(client, "_backend", None)
    acquire_mtu = getattr(backend, "_acquire_mtu", None)
    if acquire_mtu is None:
        record["error"] = "backend_has_no_acquire_mtu"
        capture["mtu_negotiation"] = record
        return 20

    record["attempted"] = True
    try:
        await acquire_mtu()
        record["ok"] = True
    except Exception as exc:  # pragma: no cover - depends on BlueZ/device state
        record["error"] = repr(exc)

    mtu_size = getattr(backend, "_mtu_size", None)
    if record["ok"]:
        try:
            mtu_size = client.mtu_size
        except Exception as exc:  # pragma: no cover - defensive for backend quirks
            record["mtu_read_error"] = repr(exc)

    if isinstance(mtu_size, int) and mtu_size > 3:
        record["mtu_size"] = mtu_size
        record["payload"] = mtu_size - 3
    record["meets_required"] = record["payload"] >= required_payload
    capture["mtu_negotiation"] = record
    if record["ok"]:
        print(
            f"negotiated MTU={record['mtu_size']} "
            f"payload={record['payload']} required={required_payload}"
        )
    else:
        print(
            f"could not negotiate large-write MTU; using payload={record['payload']} "
            f"required={required_payload}"
        )
    return int(record["payload"])


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

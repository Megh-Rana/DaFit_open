"""Experimental BLE scanner/prober for CRP/Da Fit compatible watches."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

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
    QUERY_DEVICE_VERSION,
    QUERY_DISPLAY_WATCH_FACE,
    QUERY_WATCH_FACE_LIST,
    QUERY_WATCH_FACE_SCREEN,
    decode_frame,
    hex_bytes,
    parse_frame,
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
) -> None:
    device: BLEDevice | str
    if direct:
        print(f"using direct address connection for {address}")
        device = address
    else:
        found_device = await _find_device(address, scan_timeout)
        if found_device is None:
            print(f"device not found during {scan_timeout:.1f}s scan: {address}")
            return
        device = found_device

    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"connecting to {_device_label(device)}, attempt {attempt}/{retries}")
            await _probe_device(device, timeout, pair=pair)
            return
        except TimeoutError as exc:
            last_error = exc
            print(f"connect timed out after {timeout:.1f}s")
        except Exception as exc:
            last_error = exc
            print(f"connect/probe failed: {type(exc).__name__}: {exc}")

        if attempt < retries:
            await asyncio.sleep(2)
            if not direct:
                refreshed = await _find_device(address, scan_timeout)
                if refreshed is not None:
                    device = refreshed

    print("probe failed after all retries")
    if last_error is not None:
        print(f"last error: {type(last_error).__name__}: {last_error}")


async def _probe_device(device: BLEDevice | str, timeout: float, pair: bool) -> None:
    async with BleakClient(device, timeout=timeout, pair=pair) as client:
        print(f"connected: {client.is_connected}")

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

        for char in notify_chars:
            await client.start_notify(char, _notification_handler)
            print(f"notify enabled: {char.uuid}")

        if write_char is None:
            print("no primary write characteristic found; stopping after discovery")
            return

        await _send_queries(
            client,
            write_char,
            write_with_response=write_with_response,
            mtu_payload=_guess_mtu_payload(client),
        )
        await asyncio.sleep(5)

        for char in notify_chars:
            await client.stop_notify(char)


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
    raw = bytes(data)
    frame = parse_frame(raw)
    suffix = ""
    if frame is not None:
        suffix = f"  frame flags=0x{frame.flags:02X} len={frame.packet_len} cmd=0x{frame.command:02X}"
        decoded = decode_frame(frame)
        if decoded:
            suffix += f"  {decoded}"
    print(f"<< {sender}: {hex_bytes(raw)}{suffix}")


async def _send_queries(
    client: BleakClient,
    write_char: object,
    write_with_response: bool,
    mtu_payload: int,
) -> None:
    for packet in [
        QUERY_DEVICE_VERSION,
        QUERY_DISPLAY_WATCH_FACE,
        QUERY_WATCH_FACE_LIST,
        QUERY_WATCH_FACE_SCREEN,
    ]:
        await _write_packet(client, write_char, packet, write_with_response, mtu_payload)
        await asyncio.sleep(0.5)


async def _write_packet(
    client: BleakClient,
    write_char: object,
    packet: Packet,
    write_with_response: bool,
    mtu_payload: int,
) -> None:
    data = packet.__class__(packet.command, packet.payload, mtu_payload).build()
    print(f">> cmd=0x{packet.command:02X}: {hex_bytes(data)}")
    await client.write_gatt_char(write_char, data, response=write_with_response)


def _can_write(properties: Iterable[str]) -> bool:
    return "write" in properties or "write-without-response" in properties


def _guess_mtu_payload(client: BleakClient) -> int:
    # BlueZ warns when reading BleakClient.mtu_size before explicitly acquiring
    # MTU. Stay in the default 20-byte payload mode until we need large writes.
    return 20

"""Experimental BLE scanner/prober for CRP/Da Fit compatible watches."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from bleak import BleakClient, BleakScanner

from .protocol import (
    ALT_CHARACTERISTIC_4A02,
    BATTERY_LEVEL,
    CRP_HISILICON,
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
    hex_bytes,
    parse_frame_prefix,
)


NOTIFY_UUIDS = {
    CRP_NOTIFY_PRIMARY,
    CRP_NOTIFY_SECONDARY,
    CRP_NOTIFY_EXT_1,
    CRP_NOTIFY_EXT_2,
    CRP_HISILICON,
    BATTERY_LEVEL,
    HEART_RATE_MEASUREMENT,
    ALT_CHARACTERISTIC_4A02,
}


async def scan(timeout: float = 10.0) -> None:
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for device, adv in devices.values():
        name = device.name or adv.local_name or "<unknown>"
        uuids = ", ".join(adv.service_uuids or [])
        print(f"{device.address}  RSSI={adv.rssi:>4}  {name}")
        if uuids:
            print(f"  services: {uuids}")


async def probe(address: str, timeout: float = 20.0) -> None:
    async with BleakClient(address, timeout=timeout) as client:
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


def _notification_handler(sender: object, data: bytearray) -> None:
    raw = bytes(data)
    parsed = parse_frame_prefix(raw)
    suffix = ""
    if parsed is not None:
        flags, packet_len, command = parsed
        suffix = f"  frame flags=0x{flags:02X} len={packet_len} cmd=0x{command:02X}"
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
    mtu = getattr(client, "mtu_size", None)
    if isinstance(mtu, int) and mtu > 23:
        return max(20, mtu - 3)
    return 20

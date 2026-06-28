# Protocol Discovery Notes

These notes describe observed behavior and are not copied app code.

## Decompiled APK Context

APK inspected:

`com.crrepa.band.dafit_v2.8.4-186-g43ae5fb5ce-15983_minAPI19(arm64-v8a)(nodpi)_apkmirror.com.apk`

JADX output used as reference:

`/home/megh/projects/DaFIT_Decomp/decompiled/dafit_jadx`

Useful reference points in the decompiled tree:

- Public BLE API: `com.crrepa.ble.CRPBleClient`
- Public connection API: `com.crrepa.ble.conn.CRPBleConnection`
- Internal connection implementation: `y9.a`, `y9.b`, `y9.c`, `y9.d`
- GATT service mapping: `va.b`, `va.c`
- Packet builders: `u9.*`, especially `u9.a2`
- Notification router/parser: `ka.a`
- Write queue/sender: `ka.f`, `ta.*`

## Main BLE Flow

Observed internal flow:

1. `CRPBleClient.create(context)` wraps Android Bluetooth APIs.
2. `getBleDevice(address)` returns a `CRPBleDevice` wrapper.
3. `CRPBleDevice.connect()` connects GATT and returns a `CRPBleConnection`.
4. On connection, services are discovered after a short delay.
5. The app enables notifications on several known characteristics.
6. It reads/probes protocol state, requests MTU, then reports connected.

## Main GATT Shape

The normal device-control service appears to be a 16-bit service:

- Service: `0000feea-0000-1000-8000-00805f9b34fb`

Required characteristics:

- `fee1`
- `fee2`
- `fee3`

Optional/extended characteristics:

- `fee5`
- `fee6`
- `fee7`
- `fee8`
- `fee9`

Other observed standard/auxiliary services:

- Battery: `180f`, characteristic `2a19`
- Device information: `180a`, characteristics `2a24`, `2a28`, `2a29`
- Heart rate: `180d`, characteristic `2a37`
- Auxiliary service: `3802`, characteristic `4a02`

## Common Packet Frame

Most command packets use this frame:

```text
FE EA flags length command payload...
```

Length includes the 5-byte header. In default 20-byte BLE payload mode, `flags`
is `0x10`. In larger-MTU mode, `flags` is `0x20` plus the high length byte.

Examples represented by our clean code:

- Query device version: command `0x2E`, no payload.
- Query display watch face: command `0xB4`, payload `00`.
- Query watch face list: command `0xA6`, payload `01`.

## Next Validation

Run:

```bash
dafit-open scan
dafit-open probe <watch-address>
```

Capture:

- Advertised name and service UUIDs.
- Full GATT service list.
- Notification bytes after enabling notifications.
- Responses to the initial query packets.

Add the captured bytes to a separate local log first. Only promote stable,
non-private protocol facts into these docs.

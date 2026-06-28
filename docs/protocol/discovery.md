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

## FireBoltt 148 Advertisement

Observed from a local `dafit-open scan --verbose` run:

- Address: `D3:05:F5:F9:B3:E5`
- Address type: public
- Name: `FireBoltt 148`
- Advertised service UUID: `0000feea-0000-1000-8000-00805f9b34fb`
- Manufacturer data company/id: `0xf0ef`
- Manufacturer data payload: `D3 05 F5 F9 B3 E5`
- Service data for `feea`: `45 45 53 03 04 00 10`
- Advertising flags: `02`
- BlueZ cache state during scan: unpaired, unbonded, untrusted, unconnected,
  services unresolved

The watch also appears to have a separate "phone and media" mode for classic
Bluetooth audio/calls. That mode is distinct from the BLE `feea` companion-app
interface. Enabling phone/media may expose speaker/headset profiles, but it is
not expected to be required for app-style BLE data, settings, health sync, or
watch-face transfer.

In `bluetoothctl`, a previously discovered BLE device may appear as `[CHG]`
instead of `[NEW]`. For example, seeing:

```text
[CHG] Device D3:05:F5:F9:B3:E5 RSSI: ...
```

still means BlueZ is receiving advertisements for that BLE address.

Nearby related device:

- `DF:60:6F:58:E5:F6`, `FireBoltt 146`
- Same `feea` service and manufacturer id `0xf0ef`
- Service data for `feea`: `45 59 4E 03 04 00 10`

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

## BlueZ Connection Timeout Notes

If scanning sees the watch but GATT connection times out before services are
resolved:

1. Turn off Bluetooth on the phone or force-close Da Fit so the watch is not
   already connected to another central.
2. Clear stale BlueZ state:

   ```bash
   bluetoothctl remove D3:05:F5:F9:B3:E5
   ```

3. Try pairing mode:

   ```bash
   dafit-open probe D3:05:F5:F9:B3:E5 --timeout 60 --scan-timeout 15 --retries 3 --pair
   ```

4. Try direct raw-address mode:

   ```bash
   dafit-open probe D3:05:F5:F9:B3:E5 --timeout 60 --retries 3 --direct
   ```

5. Compare with BlueZ directly:

   ```bash
   bluetoothctl
   scan on
   connect D3:05:F5:F9:B3:E5
   info D3:05:F5:F9:B3:E5
   ```

Observed `bluetoothctl info` after an attempted connection to FireBoltt 148:

- Device remained `Connected: no`
- Device remained unpaired/unbonded/untrusted
- `feea` UUID, manufacturer data, and service data were still visible
- The watch disappeared and reappeared in discovery around the connection
  attempt

This means the current blocker is below the Python protocol layer: BlueZ is
able to discover the watch but is not establishing a GATT connection yet.

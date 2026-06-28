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
- Query display watch face: command `0x29`, no payload.
- Query watch face list: command `0xA6`, payload `01`.

## Next Validation

Run:

```bash
dafit-open scan
dafit-open probe <watch-address>
dafit-open device-info <watch-address>
```

Capture:

- Advertised name and service UUIDs.
- Full GATT service list.
- Notification bytes after enabling notifications.
- Responses to the initial query packets.
- Values from readable GATT characteristics.

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

Later `bluetoothctl connect D3:05:F5:F9:B3:E5` succeeded and resolved services.
Resolved state:

- `Connected: yes`
- `ServicesResolved: yes`
- Appearance: `0x00c1`
- Modalias: `bluetooth:v005Dp0000d0100`

Resolved primary services:

- `1801` Generic Attribute
- `1800` Generic Access
- `000001ff-3c17-d293-8e48-14fe2e4da212`
- `180f` Battery
- `180a` Device Information
- `0000d0ff-3c17-d293-8e48-14fe2e4da212`
- `fee7`
- `feea`
- `180d` Heart Rate
- `000002fd-3c17-d293-8e48-14fe2e4da212`

Resolved `feea` service shape on FireBoltt 148:

- `fee1`, has CCCD descriptor
- `fee2`
- `fee3`, has CCCD descriptor
- `fee5`
- `fee6`
- `fee4`

This differs slightly from the broad decompiled-app service mapper, which also
knows about optional `fee7`, `fee8`, and `fee9` characteristics under `feea`.

## First Probe Responses

Successful `dafit-open probe D3:05:F5:F9:B3:E5 --timeout 30 --retries 1`
observations:

- Notifications enabled on `2a37`, `2a19`, `fee3`, and `fee1`.
- Writes to `fee2` succeeded.
- `0x2E` query sent: `FE EA 10 05 2E`
- `0x2E` response on `fee3`: `FE EA 20 06 2E 01`
- Parsed device version payload: `1`
- `fee1` also emitted non-framed bytes: `22 01 00 F0 00 00 10 00 00`
- `0xB4 00` query sent, no response observed in this run. Later review showed
  this is not the app's current-display query.
- The app's `queryDisplayWatchFace()` sends command `0x29` with no payload.
- The app's `queryWatchFaceScreenInfo()` sends command `0xB4` payload `14`.
- `0xA6 01` watch-face-list query sent: `FE EA 10 06 A6 01`
- `0xA6` response on `fee3`:

  ```text
  FE EA 20 23 A6
  01 07
  00 41 00 01
  01 42 0C E3
  02 42 0C E4
  03 42 0C E5
  04 42 0C E6
  05 42 0C E2
  06 42 0C E1
  ```

The decompiled parser `ca.n0.m(byte[])` interprets the `0xA6` payload as:

- Byte 0: subcommand/status, expected `1`
- Byte 1: count
- Then repeated 4-byte slots: index, one-byte ASCII type, big-endian watch-face ID

Parsed slots:

- index `0`, type `A`, id `1`
- index `1`, type `B`, id `3299`
- index `2`, type `B`, id `3300`
- index `3`, type `B`, id `3301`
- index `4`, type `B`, id `3302`
- index `5`, type `B`, id `3298`
- index `6`, type `B`, id `3297`

Follow-up probe confirmed:

- `0x29` query sent: `FE EA 10 05 29`
- `0x29` response: `FE EA 20 06 29 06`
- Parsed current display slot: `6`
- Current display slot maps to watch-face id `3297` from the `0xA6` list.
- `0xB4 14` was sent as `FE EA 10 06 B4 14`; no response was observed in that
  run.

The probe supports query sets:

- `default`: device version, current display slot, watch-face list
- `watchface`: default plus screen-info query `0xB4 14`
- `watchface-support`: support-watchface cluster matching
  `querySupportWatchFace()` in the app: `0x84`, `0xB4 00`, `0xB4 12`,
  `0xB4 10`, `0xB4 20`, `0xB4 14`

Observed `watchface-support` response:

- `0x84` query sent: `FE EA 10 05 84`
- `0x84` response: `FE EA 20 08 84 FF FF 40`
- App parser path: `ka.a` case `-124` -> `L2()` -> `ca.n0.i(byte[])`
- Parsed as support-watch-face info:
  - display index: `65535`
  - supported values: `[64]`
- `0xB4 00`, `0xB4 12`, `0xB4 10`, `0xB4 20`, and `0xB4 14` produced no
  response in this run.

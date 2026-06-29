# Watch-Face Transfer Notes

These notes describe observed packet builders and transfer flow from the
decompiled app. They are not copied app code.

## Confirmed Control Command

The active watch-face slot is controlled by command `0x19`:

```text
FE EA 10 06 19 <slot>
```

FireBoltt 148 confirmation:

- Sending slot `5` changed the visible face.
- Follow-up `0x29` query returned `display_watch_face=5`.
- Sending slot `6` also worked and restored the previous active slot.

## Transfer Overview

The app's default watch-face send path is:

1. `CRPBleConnection.sendWatchFace(CRPWatchFaceInfo, listener, timeout)`
2. `y9.a.sendWatchFace(...)`
3. `oa.g.c(...)` selects a transfer implementation based on watch-face type.
4. File transfer uses `ua.c.b().a(type)` to create a `ua.b` sender.
5. `ua.b` sends command `0xB7` packets for file start/check/abort.

The `CRPWatchFaceInfo` type enum has:

- `DEFAULT`
- `SIFLI`
- `JIELI`
- `HISILICON`

The FireBoltt 148 support response currently looks Jieli-like:

- `0x84` response: `FE EA 20 08 84 FF FF 40`
- Parsed supported values: `[64]`
- The app also probes Jieli support with `0xB4 10`, though our watch did not
  respond to that query in the first capture.

## Transfer Prepare Packet

Video/gallery/photo helper classes send a prepare packet before file transfer:

```text
FE EA flags len B4 01 <total_size:uint32-le> <file_count:uint8>
```

Decompiler references:

- `oa.h.g(totalSize, fileCount)` builds `a2.b(-76, payload)`.
- `oa.d.f(totalSize, fileCount)` uses the same payload shape.
- `-76` signed byte is command `0xB4`.
- Payload byte `0` is `01`.

The Python helper `watch_face_transfer_prepare_packet(total_size, file_count)`
builds this packet, but no CLI command sends it yet.

## File Transfer Start Packet

`ua.b` is the normal BLE file sender when SPP is not active:

```text
FE EA flags len B7 00 <transfer_type:uint8> <size:uint32-le> <filename:utf8>
```

Decompiler references:

- `ua.b.getCmd()` returns `-73`, command `0xB7`.
- `ua.b.j()` builds payload:
  - byte `0`: `00`, start transfer
  - byte `1`: transfer type
  - bytes `2..5`: file size, little-endian
  - bytes `6..`: UTF-8 filename, capped at 160 bytes
- `ua.b.sendFileCheckResult(true)` sends `0xB7 03`.
- `ua.b.sendFileCheckResult(false)` sends `0xB7 04`.
- `ua.b.abort()` sends `0xB7 05`.

Observed transfer type values from helper classes:

- `9`: one watch-face path in `oa.c`
- `11`: photo watch face / fixed photo helpers
- `12`: video watch face helper
- `13`: AI watch-face helper
- `14`: AI watch-face preview path
- `17`: gallery transfer

The exact transfer type for FireBoltt 148 store watch faces is still unverified.
Do not implement full upload until we identify the correct type and capture an
app transfer or a safe test file.

## Current Python Scaffold

The CLI can now prepare a clean-room local image package and packet plan without
writing anything to the watch:

```bash
dafit-open build-watch-face photo.ppm --out-dir watch-face-package
dafit-open inspect-watch-face-package watch-face-package
dafit-open watch-face-transfer-plan watch-face-package --transfer-type 14 --packet-length 256
dafit-open upload-watch-face D3:05:F5:F9:B3:E5 watch-face-package --dry-run
```

`build-watch-face` creates:

- `face.rgb565`: resized/cropped main image, raw RGB565, little-endian by default.
- `thumb.rgb565`: resized/cropped thumbnail.
- `preview.ppm`: dependency-free preview of the processed main image.
- `manifest.json`: package metadata, sizes, and SHA-256 hashes.

`watch-face-transfer-plan` creates the currently understood packet sequence:

1. `0xB4 01 <total_size:uint32-le> <file_count:uint8>`
2. One `0xB7 00 <transfer_type:uint8> <size:uint32-le> <filename>` packet for
   each transferable file.
3. Optional wrapped chunk previews when `--packet-length` is provided.

The chunk wrapper matches the decompiled BLE file sender shape:

```text
FE <crc16:be> <len:uint8> <chunk>
```

For a negotiated packet length of `64`, the app uses a two-byte prefix:

```text
FF FF <crc16:be> <len:uint8> <chunk>
```

The CRC-16 seed is `0xFEEA`, matching the decompiled `com.crrepa.i0.e` helper.

`inspect-watch-face-package` verifies generated file sizes, SHA-256 hashes, and
CRC-16 values before a package is handed to any transfer code.

## Manual Confirmation Needed

The guarded `upload-watch-face` command currently refuses real uploads unless
run with `--dry-run`. This is intentional.

Before enabling the actual BLE write loop, we still need one of:

- A Da Fit BLE capture of a custom photo/watch-face upload on the FireBoltt 148.
- Confirmation that the watch accepts raw RGB565 files for a selected transfer
  type, followed by a small, manually supervised test.

The reason is format risk, not packet framing risk: the app appears to use
vendor-specific watch-face generators/compressors before invoking the generic
file sender. Sending a wrong-format file should be treated as a state-changing
experiment, not a normal read-only probe.

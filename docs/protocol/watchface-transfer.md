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

## App Image Compression

The photo/video/gallery helpers do not transfer raw pixels. They compress
Android bitmaps through `com.compress.api.PicZipApi` before invoking `ua.b`.

Observed clean-room facts from decompiled structure:

- `wa.c` splits an Android bitmap into alpha, red, green, and blue channels.
- Compression parameters use `modeRgb=1`, `modeAlpha=1`, `cmpMode=0`,
  `tileWidth=8`, `stride=width`, and the bitmap dimensions.
- `pixelFormat` is `1` for ARGB_8888 and `2` for RGB_565.
- Expected compressed payload size is computed as:

```text
((round_up(width, 8) * round_up(height, 4)) * 4 / 8) + 24
```

- The native libraries include `libnativelib.so` and `libezip.so`; exported
  strings reference `Java_com_compress_nativelib_NativeLib_CompressInJNI`,
  `Java_com_sifli_ezip_sifliEzipUtil_png2EzipNDK`, `encode_pixel_data_to_ezip`,
  and `RGB565`/`RGB888A`/`RGB565A` formats.

The clean-room Python package currently writes raw RGB565 as an intermediate
format. It does not yet generate the ezip `.bin` payload expected by the app
helpers.

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

## Guarded Uploader

The guarded `upload-watch-face` command can run a supervised experimental raw
transfer only when both `--confirm` and `--experimental-raw` are provided.
Without `--complete`, it sends at most `--max-chunks` file chunks and then sends
`0xB7 05` abort. The default `--max-chunks 0` is a handshake-only probe.

Useful bounded probe:

```bash
dafit-open upload-watch-face D3:05:F5:F9:B3:E5 /tmp/dafit-face-package-small \
  --confirm --experimental-raw --name-mode role --max-chunks 0 \
  --json-out ble-logs/fireboltt148-upload-handshake-small.json
```

Supervised FireBoltt 148 results on 2026-06-29:

- Transfer type `14`, filename `face.rgb565`: no `0xBA` package-length response,
  no `0xB7` offset response after start; abort sent.
- Transfer type `14`, short filename `face.bin`: same result.
- Transfer type `11`, short filename `face.bin`: same result.

This suggests format or precondition risk, not just packet framing risk. The
next required step is either:

- Generate ezip `.bin` payloads clean-room and retry a tiny bounded transfer.
- Capture an app custom-photo upload and compare packet order, filenames,
  transfer type, and compressed file bytes.

The reason is format risk, not packet framing risk: the app appears to use
vendor-specific watch-face generators/compressors before invoking the generic
file sender. Sending a wrong-format file should be treated as a state-changing
experiment, not a normal read-only probe.

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

## Store `.bin` Watch Faces

Da Fit store faces use a different transfer family from the raw `0xB4`/`0xB7`
image scaffold above. A captured app transfer for watch-face id `19719` wrote a
140,356-byte `.bin` payload in 244-byte chunks to `0000fee6`.

The store upload flow implemented in Python is:

1. Send `0x74 00 <size:uint24-be>`.
2. Send observed setup packets `0xB6 00 01`, `0xB6 01 01`, `0xBC 01 00`,
   and `0x34 00`.
3. Wait for `0x74 <chunk_index:uint16-be>`.
4. Write exactly one raw chunk of `packet_length` bytes to `0000fee6`.
5. On `0x74 FF FF <crc16:be>`, compare against the full payload CRC and send
   `0x74 00 00 00 00` on success.

FireBoltt 148 live result:

- Downloaded payload size: `140356` bytes.
- SHA-256:
  `89f21c0b9012709535cb3d13e6794b8bc99d932d1b600f599345516745dad4f3`.
- CRC-16 seed `0xFEEA`: `0xEDFA`.
- The watch requested 576 chunks, returned CRC `0xEDFA`, accepted success, and
  later reported an uploaded type `C` face.

Useful commands:

```bash
dafit-open inspect-watch-face-bin ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin
dafit-open analyze-watch-face-bin ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin
dafit-open upload-watch-face-bin D3:05:F5:F9:B3:E5 ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin \
  --confirm --complete --json-out ble-logs/fireboltt148-store-bin-upload.json
```

The analyzer currently looks for candidate header fields, zero runs, and
monotonic pointer tables. The `19719.bin` payload begins with several compact
header values and a little-endian monotonic table around offset `400`, so it
appears to be a structured store container rather than raw framebuffer pixels.

## ORIGINAL Custom Background

The custom-background app path is separate from both store `.bin` and the older
generic raw file-transfer probe. Decompiled structure shows
`CRPWatchFaceLayoutInfo.CompressionType.ORIGINAL` sending a single big-endian
RGB565 background through command `0x6E`.

Clean-room observations:

- Source bitmap is cropped/scaled to the layout size.
- FireBoltt 148 layout logs reported `width=466`, `height=466`,
  `thumWidth=280`, and `thumHeight=280`.
- ORIGINAL pixels are encoded as RGB565 in big-endian byte order.
- Da Fit avoids the RGB565 value `0x0821` by incrementing it to `0x0822`;
  `08 21` is also the RLE marker used by the optional compressed encoder.
- Da Fit sends the normal photo-face layout packet (`cmd=0x38`) before
  background upload. The payload is time position, top/bottom content,
  big-endian RGB565 text color, then 32 MD5 nibbles.
- The size packet is `0x6E <size:uint32-be>`. Current live evidence indicates
  this size is the number of bytes written to the transfer characteristic,
  including the per-chunk wrapper, not only raw RGB565 image bytes.
- Check packets use command `0x6E` with `00 00 00 00` for success and
  `FF FF FF FF` for failure.
- Data chunks use the same BLE file chunk wrapper as `ua.b`:
  `FE <crc16:be> <len:uint8> <chunk>` or
  `FF FF <crc16:be> <len:uint8> <chunk>` for packet length `64`.

For a 466x466 ORIGINAL background, the raw payload size is:

```text
466 * 466 * 2 = 434312 bytes
```

With 240-byte raw chunks, each transfer write is `244` bytes
(`FE <crc16:be> <len:uint8>` plus `240` data bytes). The announced transfer
size is therefore:

```text
434312 + (1810 * 4) = 441552 bytes
```

The expected size packet for that plan is:

```text
FE EA 10 09 6E 00 06 BC D0
```

The final CRC/status packet also checks the wrapped transfer stream. For the
current circular-mask test package:

```text
raw RGB565 CRC:      0x7F27
wrapped stream CRC:  0x4987
watch returned CRC:  0x4987
```

Dry-run commands:

```bash
dafit-open build-original-background photo.png --out-dir /tmp/dafit-original-bg
dafit-open original-background-transfer-plan /tmp/dafit-original-bg --packet-length 240
dafit-open upload-original-background D3:05:F5:F9:B3:E5 /tmp/dafit-original-bg --dry-run
```

Bounded live handshake:

```bash
dafit-open upload-original-background D3:05:F5:F9:B3:E5 /tmp/dafit-original-bg \
  --confirm --experimental-original --max-chunks 0 \
  --json-out ble-logs/fireboltt148-original-background-handshake.json
```

FireBoltt 148 live observations:

- After the `0x6E` size packet, the watch responded with
  `FE EA 20 07 6E 00 00`.
- This is parsed as `watch_face_background_chunk_index index=0`.
- Sending one wrapped 64-byte chunk produced the next request:
  `FE EA 20 07 6E 00 01`.
- No `0xBA` packet-length response was observed. The uploader now falls back to
  the largest wrapped chunk that fits one negotiated GATT write. On FireBoltt
  148 with MTU payload `244`, that is `240` data bytes:
  `FE <crc16:be> <len:uint8> <240 bytes>`.
- At 466 x 466 RGB565, the raw payload is fixed at `434312` bytes. The 240-byte
  fallback gives `1810` expected raw chunks before check/status, compared with
  `6787` chunks at the original 64-byte fallback.
- Bounded probes then sent `0x6E FF FF FF FF` to fail/abort cleanly.
- A full 64-byte fallback attempt reached chunk index `6294` and then returned
  `FE EA 20 09 6E FF FF 00 00`, parsed as CRC/status `0x0000`; this is treated
  as rejection, not success.
- A full 240-byte fallback attempt reached chunk index `1779` and then returned
  the same `FE EA 20 09 6E FF FF 00 00` rejection. Both failures line up with
  the point where wrapped transfer bytes crossed the raw `434312` size we had
  announced. The uploader now announces the wrapped transfer size instead.
- With wrapped-size announcement, the watch requested the final raw chunk index
  `1809` and returned CRC `0x4987`, which matches the wrapped transfer stream.
  The uploader now compares ORIGINAL background CRCs against the wrapped stream
  rather than the raw RGB565 payload.

The decompiled app photo crop helper uses cover-style scaling and switches to a
circle crop style for round watch profiles. The CLI can mirror those prep steps:

```bash
dafit-open build-original-background photo.png --out-dir /tmp/dafit-original-bg \
  --fit cover --circular-mask
dafit-open upload-original-background D3:05:F5:F9:B3:E5 /tmp/dafit-original-bg \
  --confirm --experimental-original --complete --compact-capture \
  --json-out ble-logs/fireboltt148-original-background-compact.json
```

Run `--complete` only as a supervised probe with a reviewed package and capture
path, because it streams enough data for the watch to attempt applying the
custom background.

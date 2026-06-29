# dafit-open

Clean-room experiments for talking to Da Fit / CRREPA-style smart watches over BLE.

This repository is for new code and notes only. Do not copy decompiled app source,
assets, strings, or proprietary resources into this tree.

## Current Goal

Build the smallest useful BLE path:

1. Scan for nearby watches.
2. Connect to a chosen MAC/address.
3. Discover GATT services and characteristics.
4. Enable notifications.
5. Send harmless query commands, starting with device/version and watch-face list.
6. Document observed request/response bytes.

## Setup

```bash
cd /home/megh/projects/DaFIT_Decomp/dafit-open
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Scan:

```bash
dafit-open scan
```

Probe a device:

```bash
dafit-open probe AA:BB:CC:DD:EE:FF
```

Read all readable GATT characteristics without sending protocol commands:

```bash
dafit-open device-info AA:BB:CC:DD:EE:FF
```

Run extra watch-face queries:

```bash
dafit-open watch-faces AA:BB:CC:DD:EE:FF --json-out ble-logs/watch-faces.json
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface-support
```

Run read-oriented health/data discovery queries:

```bash
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-history
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-basic
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-extended
dafit-open probe AA:BB:CC:DD:EE:FF --query-set settings-basic
dafit-open probe AA:BB:CC:DD:EE:FF --query-set daily-settings
dafit-open probe AA:BB:CC:DD:EE:FF --query-set alarms
```

Query stored workout details after `health-history` reports training IDs:

```bash
dafit-open training-detail AA:BB:CC:DD:EE:FF 11 12 13 14
dafit-open training-series AA:BB:CC:DD:EE:FF 11 --kind all
dafit-open sync-training AA:BB:CC:DD:EE:FF --json-out ble-logs/training-sync.json
```

Collect the currently implemented app-style data in one workflow:

```bash
dafit-open collect AA:BB:CC:DD:EE:FF --out-dir ble-logs/current --export-state exports/app-state.json
dafit-open collect AA:BB:CC:DD:EE:FF --no-training --out-dir ble-logs/current-fast
```

Set the active watch-face slot after confirming the slot list:

```bash
dafit-open set-watch-face AA:BB:CC:DD:EE:FF 5 --confirm
```

Build an experimental local image package for a future custom watch face:

```bash
dafit-open build-watch-face photo.ppm --out-dir watch-face-package
dafit-open inspect-watch-face-package watch-face-package
dafit-open watch-face-transfer-plan watch-face-package --transfer-type 14 --packet-length 256
dafit-open upload-watch-face AA:BB:CC:DD:EE:FF watch-face-package --dry-run
```

PPM input works without optional dependencies. PNG/JPEG input needs Pillow:

```bash
pip install -e ".[image]"
dafit-open build-watch-face photo.png --out-dir watch-face-package
```

Real image upload is guarded behind explicit experimental flags. The current
commands build raw RGB565 files, generate the observed `0xB4`/`0xB7` transfer
packets, and can run bounded supervised handshakes:

```bash
dafit-open upload-watch-face AA:BB:CC:DD:EE:FF watch-face-package \
  --confirm --experimental-raw --name-mode role --max-chunks 0 \
  --json-out ble-logs/watch-face-upload-handshake.json
```

Supervised raw RGB565 handshakes against FireBoltt 148 did not receive
`0xBA` package-length or `0xB7` file-offset responses for transfer types `14`
or `11`. The app appears to compress images to an ezip `.bin` payload before
transfer, so full upload should wait until we can generate that clean-room
container or capture an app upload.

Import Da Fit app logs pulled from Android app storage into a clean-room BLE
capture. When the app log contains `BleLog` transfer writes, this also rebuilds
the raw stream that Da Fit sent over `0000fee6`:

```bash
dafit-open import-app-log ../logs/dafit-android-data/files/moy_logs/2026-06-29/log_16-15-00.txt \
  --output ble-logs/app-log-watchface-upload.json \
  --out-dir ble-logs/app-log-watchface-upload
```

The first captured store-face upload used `/data/user/0/com.crrepa.band.dafit/files/crrepa/band/wf/19719.bin`,
streamed 576 transfer chunks, and rebuilt a 140,356-byte payload from the app
log. This gives us a replay/decode target without copying proprietary app code.

Download and inspect a store watch-face `.bin` payload:

```bash
dafit-open download-watch-face-bin https://qn-hscdn2.moyoung.com/files/77e6d813b1f8aa283d7265f051d62e13.bin \
  --output ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin
dafit-open inspect-watch-face-bin ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin
dafit-open watch-face-bin-transfer-plan ble-logs/moyoung-downloads/77e6d813b1f8aa283d7265f051d62e13.bin
```

Upload of store `.bin` payloads is guarded and experimental. Da Fit transfers
these files as 244-byte writes to `0000fee6`, so this command negotiates a large
MTU first and stops before transfer if BlueZ cannot provide a 244-byte payload:

```bash
dafit-open upload-watch-face-bin AA:BB:CC:DD:EE:FF path/to/watch-face.bin \
  --dry-run
dafit-open upload-watch-face-bin AA:BB:CC:DD:EE:FF path/to/watch-face.bin \
  --confirm --max-chunks 0 --json-out ble-logs/store-bin-handshake.json
dafit-open upload-watch-face-bin AA:BB:CC:DD:EE:FF path/to/watch-face.bin \
  --confirm --complete --set-display 6 --json-out ble-logs/store-bin-upload.json
```

FireBoltt 148 store `.bin` upload has been live-tested with the downloaded
19719 face. The watch accepted all 576 chunks, returned the expected CRC, and
reported the uploaded face as a new type `C` slot afterward.

Build a clean-room custom ORIGINAL background package from an image. This path
comes from the app's `CompressionType.ORIGINAL` custom-background flow and
writes a single big-endian RGB565 `background.rgb565` payload:

```bash
dafit-open build-original-background photo.png --out-dir original-background-package
dafit-open original-background-transfer-plan original-background-package --packet-length 64
dafit-open upload-original-background AA:BB:CC:DD:EE:FF original-background-package --dry-run
```

The live ORIGINAL uploader is newly reverse engineered, so start with the
handshake-only mode. It sends the `0x6E` background-size packet, listens for the
watch's transfer event shape, and stops before streaming image data:

```bash
dafit-open upload-original-background AA:BB:CC:DD:EE:FF original-background-package \
  --confirm --experimental-original --max-chunks 0 \
  --json-out ble-logs/original-background-handshake.json
```

Save structured captures under the ignored `ble-logs/` folder:

```bash
dafit-open device-info AA:BB:CC:DD:EE:FF --json-out ble-logs/device-info.json
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface-support --json-out ble-logs/watchface-support.json
dafit-open training-detail AA:BB:CC:DD:EE:FF 11 --json-out ble-logs/training-detail-11.json
dafit-open training-series AA:BB:CC:DD:EE:FF 11 --kind heart-rate --json-out ble-logs/training-hr-11.json
dafit-open set-watch-face AA:BB:CC:DD:EE:FF 5 --confirm --json-out ble-logs/set-watch-face-5.json
```

Export captured workout data:

```bash
dafit-open export-captures ble-logs --format json --output exports/workouts.json
dafit-open export-captures ble-logs --format csv --output exports/workouts.csv
dafit-open export-captures ble-logs --no-samples
```

Browse captured workout data in a read-only terminal UI:

```bash
dafit-open tui ble-logs
```

On wide terminals the TUI also shows the current app-state summary: device,
battery, watch-face slots/support, settings, alarms, and workout count.

Export captured watch-face state:

```bash
dafit-open export-watch-faces ble-logs --output exports/watch-faces.json
dafit-open export-settings ble-logs --output exports/settings.json
dafit-open export-alarms ble-logs --output exports/alarms.json
```

Set basic settings after checking current values:

```bash
dafit-open set-settings AA:BB:CC:DD:EE:FF --goal-steps 10000 --display-time on --confirm
dafit-open set-settings AA:BB:CC:DD:EE:FF --dnd 00:00 00:00 --confirm
```

Review alarm write packets before changing the watch:

```bash
dafit-open set-alarm AA:BB:CC:DD:EE:FF --id 3 --time 08:00 --everyday --dry-run
dafit-open delete-alarm AA:BB:CC:DD:EE:FF --id 3 --dry-run
```

Apply alarm changes only after reviewing the packet bytes:

```bash
dafit-open set-alarm AA:BB:CC:DD:EE:FF --id 3 --time 08:00 --everyday --confirm
dafit-open delete-alarm AA:BB:CC:DD:EE:FF --id 3 --confirm
```

Export one app-ready state document:

```bash
dafit-open export-state ble-logs --output exports/app-state.json
dafit-open summary ble-logs
dafit-open summary ble-logs --json --output exports/app-summary.json
```

For Linux/BlueZ connection timeouts, keep the watch awake/nearby and try:

```bash
dafit-open probe AA:BB:CC:DD:EE:FF --timeout 60 --scan-timeout 15 --retries 5
```

Useful diagnostics/workarounds:

```bash
dafit-open scan --timeout 15 --verbose
dafit-open probe AA:BB:CC:DD:EE:FF --timeout 60 --scan-timeout 15 --retries 3 --pair
dafit-open probe AA:BB:CC:DD:EE:FF --timeout 60 --retries 3 --direct
bluetoothctl remove AA:BB:CC:DD:EE:FF
```

If Bleak still times out, compare with BlueZ directly:

```bash
bluetoothctl
scan on
connect AA:BB:CC:DD:EE:FF
info AA:BB:CC:DD:EE:FF
```

The probe currently enumerates services, enables likely notification
characteristics, sends read-only query packets, and can save decoded packet
captures for later analysis.

## Interface Plan

- CLI remains the primary testing and automation interface.
- The TUI is read-only for now and calls the same capture/export model instead
  of reimplementing protocol parsing.
- A future Android app should sit on top of the same clean-room protocol model
  once data collection, watch-face transfer, and sync flows are stable.

## Repo Layout

- `src/dafit_open/protocol.py`: packet framing and known UUID constants.
- `src/dafit_open/ble_probe.py`: BLE scan/connect/probe logic.
- `src/dafit_open/watchface_image.py`: local watch-face image package and
  transfer-plan helpers.
- `docs/protocol/alarms.md`: alarm packet notes.
- `docs/protocol/daily-settings.md`: quick-view/reminder/settings packet notes.
- `docs/protocol/discovery.md`: current reverse-engineering notes.
- `docs/protocol/health-sync.md`: health/data sync packet notes.
- `docs/protocol/settings.md`: settings packet notes.
- `docs/protocol/watchface-transfer.md`: watch-face transfer packet notes.

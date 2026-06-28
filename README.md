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
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface-support
```

Run read-oriented health/data discovery queries:

```bash
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-history
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-basic
dafit-open probe AA:BB:CC:DD:EE:FF --query-set health-extended
```

Query stored workout details after `health-history` reports training IDs:

```bash
dafit-open training-detail AA:BB:CC:DD:EE:FF 11 12 13 14
dafit-open training-series AA:BB:CC:DD:EE:FF 11 --kind all
```

Set the active watch-face slot after confirming the slot list:

```bash
dafit-open set-watch-face AA:BB:CC:DD:EE:FF 5 --confirm
```

Save structured captures under the ignored `ble-logs/` folder:

```bash
dafit-open device-info AA:BB:CC:DD:EE:FF --json-out ble-logs/device-info.json
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface-support --json-out ble-logs/watchface-support.json
dafit-open training-detail AA:BB:CC:DD:EE:FF 11 --json-out ble-logs/training-detail-11.json
dafit-open training-series AA:BB:CC:DD:EE:FF 11 --kind heart-rate --json-out ble-logs/training-hr-11.json
dafit-open set-watch-face AA:BB:CC:DD:EE:FF 5 --confirm --json-out ble-logs/set-watch-face-5.json
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

## Repo Layout

- `src/dafit_open/protocol.py`: packet framing and known UUID constants.
- `src/dafit_open/ble_probe.py`: BLE scan/connect/probe logic.
- `docs/protocol/discovery.md`: current reverse-engineering notes.
- `docs/protocol/health-sync.md`: health/data sync packet notes.
- `docs/protocol/watchface-transfer.md`: watch-face transfer packet notes.

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

Run extra watch-face queries:

```bash
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface
dafit-open probe AA:BB:CC:DD:EE:FF --query-set watchface-support
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
characteristics, and sends a couple of read-only query packets.

## Repo Layout

- `src/dafit_open/protocol.py`: packet framing and known UUID constants.
- `src/dafit_open/ble_probe.py`: BLE scan/connect/probe logic.
- `docs/protocol/discovery.md`: current reverse-engineering notes.

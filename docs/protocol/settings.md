# Settings Packet Notes

These notes describe simple settings packets identified from decompiled packet
builders and clean-room Python packet construction. State-changing packets are
implemented as builders, but the normal CLI does not send them without an
explicit feature command.

## Read-Oriented Queries

The `settings-basic` probe sends these read-oriented queries:

- Goal steps: command `0x26`, no payload.
- Time system: command `0x27`, no payload.
- Display-time setting: command `0x28`, no payload.
- Do-not-disturb period: command `0x81`, no payload.

Run:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --query-set settings-basic \
  --timeout 45 --retries 1 --json-out ble-logs/fireboltt148-settings-basic.json
```

Live FireBoltt 148 result:

- Goal steps: `10000`
- Time system: `1`
- Display-time setting: enabled
- Do-not-disturb period: `00:00` to `00:00`

## Packet Builders

Implemented but not automatically sent:

- Set goal steps: command `0x16`, payload `<steps:uint32-be>`.
- Set time system: command `0x17`, payload `<0|1>`.
- Set display-time setting: command `0x18`, payload `<0|1>`.
- Set current time: command `0x31`, payload `<timestamp:uint32-be> 08`.
- Set timezone: command `0xBB`, payload `07 00 <offset_seconds:int32-le>`.
- Set DND period: command `0x71`, payload `<start_h> <start_m> <end_h> <end_m>`.

The current-time builder mirrors the app's observed GMT+8-normalized timestamp
shape. Treat it as experimental until verified against the watch display.

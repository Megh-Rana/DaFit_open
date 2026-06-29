# Alarm Packet Notes

These notes describe read-oriented alarm packets and clean-room parsers.

## Queries

The `alarms` probe sends:

- Legacy alarm list: command `0x21`, no payload.
- New alarm list: command `0xB9`, payload `15 04`.

Run:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --query-set alarms \
  --timeout 45 --retries 1 --json-out ble-logs/fireboltt148-alarms.json
```

Live FireBoltt 148 result:

- The legacy `0x21` query did not produce a response in the capture window.
- The new-alarm query returned `B9 15 04 00`, treated as an empty new-alarm list.

## Record Shape

Alarm records are 8 bytes:

```text
<id> <enabled> <kind> <hour> <minute> <date:uint16-be> <repeat>
```

Observed parser behavior from the app:

- `kind=0`: one-shot dated alarm; date packs year offset from 2015, month, day.
- `kind=1`: every-day alarm; repeat mode is `127`.
- Other `kind` values use the final repeat byte as the repeat mask.

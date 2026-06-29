# Alarm Packet Notes

These notes describe alarm packets and clean-room parsers/builders.

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

## Writes

Alarm write support is guarded in the CLI. Use `--dry-run` first, then rerun
with `--confirm` only after reviewing the frame bytes.

New-format create/update:

```text
cmd 0xB9 payload: 05 00 <8-byte alarm record>
```

Legacy create/update:

```text
cmd 0x11 payload: <8-byte alarm record>
```

New-format delete one:

```text
cmd 0xB9 payload: 05 02 <id>
```

New-format delete all:

```text
cmd 0xB9 payload: 05 03
```

Examples:

```bash
dafit-open set-alarm D3:05:F5:F9:B3:E5 --id 3 --time 08:00 --everyday --dry-run
dafit-open set-alarm D3:05:F5:F9:B3:E5 --id 2 --time 06:21 --date 2026-06-29 --dry-run
dafit-open delete-alarm D3:05:F5:F9:B3:E5 --id 3 --dry-run
```

The write packet builders are unit-tested, but live alarm mutation has not been
run unattended. `delete-alarm --all` should be treated as destructive and tested
only deliberately.

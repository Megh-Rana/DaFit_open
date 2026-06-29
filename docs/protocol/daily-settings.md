# Daily Settings Packet Notes

These read-oriented probes cover app settings that are separate from health
history and watch-face state.

Run:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --query-set daily-settings \
  --timeout 45 --retries 1 --json-out ble-logs/fireboltt148-daily-settings.json
```

## Queries

The `daily-settings` query set currently sends:

- Dominant hand: command `0x24`, no payload.
- Metric system: command `0x2A`, no payload.
- Display-time duration: command `0x8D`, no payload.
- Quick view / raise-to-wake toggle: command `0x28`, no payload.
- Quick view period: command `0x82`, no payload.
- Sedentary reminder toggle: command `0x2D`, no payload.
- Sedentary reminder period: command `0x83`, no payload.
- Drink water reminder: command `0x87`, payload `01`.
- New drink water reminder: command `0xBB`, payload `04 06 01`.
- Hand washing reminder: command `0x87`, payload `03`.
- Screen-off clock toggle: command `0xBB`, payload `0C 00`.
- Screen-off clock period: command `0xBB`, payload `0C 02`.
- Tap-to-wake toggle: command `0xAC`, no payload.

## Notes

The app facade names command `0x28` as quick-view. Earlier captures used the
same byte as a display-time-style toggle after writing command `0x18`, so
`dafit-open` keeps both `quick_view_enabled` and `display_time_enabled` fields
for compatibility until live captures make the naming fully clear.

`collect` now runs `settings-basic`, `daily-settings`, and `alarms` probes so
the exported app-state JSON has a broader settings surface.

## Live FireBoltt 148 Result

Capture:

```text
ble-logs/fireboltt148-daily-settings.json
```

Answered:

- `0x24`: dominant hand `0`.
- `0x2A`: metric system `0`.
- `0x8D`: display time `5`.
- `0x28`: quick view enabled.
- `0x82`: quick-view period `00:00-00:00`.
- `0x2D`: sedentary reminder disabled.
- `0x83`: sedentary period `60`, steps `50`, `10:00-22:00`.
- `0x87 01`: drink-water reminder disabled, `08:00`, count `8`, period `90`.

No response was seen in this capture window for:

- `0xBB 04 06 01` new drink-water reminder.
- `0x87 03` hand-washing reminder; the watch returned an empty `0x87` frame.
- `0xBB 0C 00` screen-off clock state.
- `0xBB 0C 02` screen-off clock time.
- `0xAC` tap-to-wake.

# Health/Data Sync Notes

These notes describe observed packet builders and parser routes from the
decompiled app. They are not copied app code.

## Day Values

`CRPHistoryDay` values:

- `0`: today
- `1`: yesterday
- `2`: the day before yesterday
- `3` through `6`: older days

`CRPCategoryHistoryDay` values used by category queries:

- today maps to payload `0`
- yesterday maps to payload `2`

## Read-Oriented Query Packets

The `health-basic` probe query set sends these packets:

- Goal step: `0x26`, no payload
- Sleep time: `0xB8`, payload `03`
- History step marker for today: `0x33`, payload `00`
- History step detail for today: `0xB6`, payload `00 00`
- History heart rate: `0xAB`, payload `00`
- History blood pressure: `0xAB`, payload `01`
- History blood oxygen: `0xAB`, payload `02`
- Last 24h blood pressure: `0x3D`, payload `00`
- Last 24h blood oxygen: `0x3E`, payload `00`
- Movement heart rate: `0x37`, no payload
- History training list: `0xB2`, payload `06`
- History training detail/list cursor: `0xB2`, payload `00`

Run:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --timeout 30 --retries 1 \
  --query-set health-basic \
  --json-out ble-logs/fireboltt148-health-basic.json
```

## Decompiled References

- `y9.a.queryGoalStep()` sends `u9.g0.b()` -> command `0x26`.
- `y9.a.querySleepTime()` sends `u9.h0.a()` -> command `0xB8`, payload `03`.
- `y9.a.queryHistoryStep(day)` sends `u9.q0.a(day)` and `u9.q0.b(day)`.
- `u9.q0.a(0)` -> command `0x33`, payload `00`.
- `u9.q0.b(0)` -> command `0xB6`, payload `00 00`.
- `y9.a.queryHistoryHeartRate()` sends `u9.v0.a()` -> command `0xAB`, payload `00`.
- `y9.a.queryHistoryBloodPressure()` sends `u9.f0.a()` -> command `0xAB`, payload `01`.
- `y9.a.queryHistoryBloodOxygen()` sends `u9.b0.d()` -> command `0xAB`, payload `02`.
- `y9.a.queryLast24HourBloodPressure()` sends `u9.f0.b(0)` -> command `0x3D`, payload `00`.
- `y9.a.queryLast24HourBloodOxygen()` sends `u9.b0.h(0)` -> command `0x3E`, payload `00`.
- `y9.a.queryMovementHeartRate()` sends `u9.v0.f()` -> command `0x37`.
- `y9.a.queryHistoryTraining()` sends `u9.l1.f()` and `u9.l1.a()` -> command
  `0xB2`, payloads `06` and `00`.

## Parser Routes

- Command `0x33` routes to `ka.a.K2(byte[])`, which handles step and sleep
  history markers.
- Command `0xB6` routes to `ka.a.j(byte[])`, which handles step, sleep, and
  timing-heart-rate history details depending on payload byte `0`.
- Command `0xAB` routes to `ka.a.z(byte[])`, where payload byte `0` selects
  heart rate, blood pressure, or blood oxygen history.
- Command `0xB8` routes to `ka.a.h(byte[])`; subcommand `3` is sleep time.
- Command `0xB2` routes to `ka.a.a3(byte[])`, used by training history.

The current Python decoder only labels these frames and captures raw payloads.
Full parsers should be added only after we collect live samples.

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

The `health-history` probe query set sends the packets that answered on
FireBoltt 148:

- Goal step: `0x26`, no payload
- History heart rate: `0xAB`, payload `00`
- History blood pressure: `0xAB`, payload `01`
- History blood oxygen: `0xAB`, payload `02`
- History training detail/list cursor: `0xB2`, payload `00`

The `health-extended` probe query set sends timing/last-24h candidates that
were silent in early FireBoltt 148 captures:

- Sleep time: `0xB8`, payload `03`
- History step marker for today: `0x33`, payload `00`
- History step detail for today: `0xB6`, payload `00 00`
- Last 24h blood pressure: `0x3D`, payload `00`
- Last 24h blood oxygen: `0x3E`, payload `00`
- Movement heart rate: `0x37`, no payload
- History training list: `0xB2`, payload `06`

The `health-basic` query set sends both groups.

The targeted `training-detail` command sends stored training detail requests:

- Stored training detail: `0xB2`, payload `02 <id>`

Run:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --timeout 30 --retries 1 \
  --query-set health-history \
  --json-out ble-logs/fireboltt148-health-history.json
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
- `u9.l1.b(id)` sends command `0xB2`, payload `02 <id>`, to request one stored
  training detail.
- `u9.l1.e(id, offset)`, `u9.l1.g(id, offset)`, and `u9.l1.c(id, offset)` send
  `0xB2` payloads `04`, `07`, and `09` for training heart-rate, step, and
  distance chunks. The offset is encoded as a big-endian uint16.

## Parser Routes

- Command `0x33` routes to `ka.a.K2(byte[])`, which handles step and sleep
  history markers.
- Command `0xB6` routes to `ka.a.j(byte[])`, which handles step, sleep, and
  timing-heart-rate history details depending on payload byte `0`.
- Command `0xAB` routes to `ka.a.z(byte[])`, where payload byte `0` selects
  heart rate, blood pressure, or blood oxygen history.
- Command `0xB8` routes to `ka.a.h(byte[])`; subcommand `3` is sleep time.
- Command `0xB2` routes to `ka.a.a3(byte[])`, used by training history. Payload
  byte `1` parses the training list, byte `3` parses one training detail, and
  bytes `5`, `8`, and `10` parse heart-rate, step, and distance responses. The
  matching requests use payload bytes `4`, `7`, and `9`.

## FireBoltt 148 Health-Basic Capture

Observed from:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --timeout 30 --retries 1 \
  --query-set health-basic \
  --json-out ble-logs/fireboltt148-health-basic.json
```

Responses:

- Goal step query `0x26` returned `FE EA 20 09 26 10 27 00 00`, decoded as
  `goal_step=10000`.
- History heart-rate query `0xAB 00` returned four records. Observed layout:
  `kind=00`, then `count`, then repeated `(bpm:uint8, timestamp:uint32-le)`.
- History blood-pressure query `0xAB 01` returned two records. Observed layout:
  `kind=01`, then `count`, then repeated
  `(systolic:uint8, diastolic:uint8, timestamp:uint32-le)`.
- History blood-oxygen query `0xAB 02` returned `FE EA 20 07 AB 02 00`, decoded
  as zero records.
- Training query `0xB2 00` returned a payload beginning with `01`. Confirmed
  layout: first byte `01`, then repeated
  `(timestamp:uint32-le seconds, type:uint8)`. The record id is the zero-based
  5-byte record index.

The same response set repeated in a second `health-basic` capture:

- `0x26`, `0xAB 00`, `0xAB 01`, `0xAB 02`, and `0xB2 00` answered.
- The decoded heart-rate, blood-pressure, blood-oxygen, and training payloads
  matched the first capture.

Silent in both runs:

- Sleep time `0xB8 03`
- History step marker `0x33 00`
- History step detail `0xB6 00 00`
- Last 24h blood pressure `0x3D 00`
- Last 24h blood oxygen `0x3E 00`
- Movement heart rate `0x37`
- History training list `0xB2 06`

The `0xAB` history timestamps decode as Unix seconds. Their year/month/day
values were plausible for existing historical records, so the Python decoder now
prints them as UTC ISO timestamps.

## FireBoltt 148 Health-History Capture

Observed from:

```bash
dafit-open probe D3:05:F5:F9:B3:E5 --timeout 30 --retries 1 \
  --query-set health-history \
  --json-out ble-logs/fireboltt148-health-history.json
```

Responses:

- Goal step: `goal_step=10000`.
- History heart rate: four records at `2026-02-10T07:18:17+00:00`,
  `2026-02-26T04:31:13+00:00`, `2026-04-11T09:36:17+00:00`, and
  `2026-04-15T02:17:13+00:00`.
- History blood pressure: two records at `2026-04-09T04:47:00+00:00` and
  `2026-04-10T07:22:24+00:00`.
- History blood oxygen: zero records.
- History training list:
  - `id=11 type=0 start=2026-02-19T23:49:19+00:00`
  - `id=12 type=0 start=2026-04-09T22:59:20+00:00`
  - `id=13 type=0 start=2026-04-10T10:19:32+00:00`
  - `id=14 type=0 start=2026-04-12T22:59:11+00:00`

Next detail probe:

```bash
dafit-open training-detail D3:05:F5:F9:B3:E5 11 12 13 14 --timeout 30 \
  --retries 1 --json-out ble-logs/fireboltt148-training-detail.json
```

## FireBoltt 148 Training-Detail Capture

Observed from:

```bash
dafit-open training-detail D3:05:F5:F9:B3:E5 11 12 13 14 --timeout 30 \
  --retries 1 --json-out ble-logs/fireboltt148-training-detail.json
```

Responses:

- `id=11`: `2026-02-19T23:49:19+00:00` to `2026-02-20T00:37:01+00:00`,
  valid time `2862`, steps `2729`, distance `2265`, calories `136`.
- `id=12`: `2026-04-09T22:59:20+00:00` to `2026-04-09T23:54:53+00:00`,
  valid time `1032`, steps `1040`, distance `863`, calories `52`.
- `id=13`: `2026-04-10T10:19:32+00:00` to `2026-04-10T10:30:09+00:00`,
  valid time `637`, steps `984`, distance `816`, calories `51`.
- `id=14`: `2026-04-12T22:59:11+00:00` to `2026-04-13T00:51:23+00:00`,
  valid time `6732`, steps `4542`, distance `3769`, calories `265`.

Next series probe:

```bash
dafit-open training-series D3:05:F5:F9:B3:E5 11 --kind all --timeout 30 \
  --retries 1 --json-out ble-logs/fireboltt148-training-series-11.json
```

The first manual `training-series` probe sent heart-rate, steps, and distance
requests without following the heart-rate cursor. The watch answered only the
heart-rate request:

- Request: `0xB2`, payload `04 0B 00 00`.
- Response: `0xB2`, payload begins `05 0B 00 87 ...`.
- Decoded: training id `11`, next offset `135`, `complete=False`, with 135
  heart-rate samples in the chunk.

Follow-up series probes should walk each series until the response offset is
`65535` before starting the next series kind.

The auto-following `training-series` probe then walked the full heart-rate
series for training id `11`:

- Heart-rate offset `0` -> response offset `135`, count `135`.
- Heart-rate offset `135` -> response offset `270`, count `135`.
- Heart-rate offset `270` -> response offset `65535`, count `18`.
- Total heart-rate samples: `288`.
- Step and distance requests at offset `0` did not answer within six seconds.

This matches the app's flow: stored training detail always fetches heart-rate
chunks first; step and distance chunks are only requested when the watch reports
a higher training-series support level from the `0xB2 06` path.

Additional heart-rate series captures:

- Training id `12`: offsets `0 -> 135 -> 270 -> 65535`; raw samples `336`,
  non-zero samples `332`.
- Training id `13`: offsets `0 -> 65535`; raw samples `64`, non-zero samples
  `62`.
- Training id `14`: offsets `0 -> 135 -> 270 -> 405 -> 540 -> 675 -> 65535`;
  raw samples `676`, non-zero samples `672`.

The `sync-training` command reproduces the same sequence in one BLE session:

```bash
dafit-open sync-training D3:05:F5:F9:B3:E5 --timeout 45 --retries 1 \
  --chunk-timeout 8 --json-out ble-logs/fireboltt148-sync-training.json
```

It discovered training ids `11`, `12`, `13`, and `14`, fetched detail for each,
and completed heart-rate series for all four ids. Exporting all captures after
this run kept the same sample counts because duplicate chunks are de-duplicated.

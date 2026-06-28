import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.capture_export import load_workout_summaries


class CaptureExportTest(unittest.TestCase):
    def test_merges_training_captures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write_capture(
                directory / "history.json",
                [
                    "01 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "00 00 00 00 00 "
                    "7F A1 97 69 00"
                ],
            )
            self._write_capture(
                directory / "detail.json",
                [
                    "03 0B 7F A1 97 69 AD AC 97 69 2E 0B 00 00 "
                    "A9 0A 00 00 D9 08 00 00 88 00 56 00 00 00 48 00"
                ],
            )
            self._write_capture(
                directory / "series.json",
                [
                    "05 0B 00 03 00 50 51",
                    "05 0B 00 03 00 50 51",
                    "05 0B FF FF 52 00 00",
                ],
            )

            workouts = load_workout_summaries([directory])

        self.assertEqual(len(workouts), 1)
        workout = workouts[0]
        self.assertEqual(workout.id, 11)
        self.assertEqual(workout.start, "2026-02-19T23:49:19+00:00")
        self.assertEqual(workout.end, "2026-02-20T00:37:01+00:00")
        self.assertEqual(workout.steps, 2729)
        self.assertEqual(workout.distance, 2265)
        self.assertEqual(workout.calories, 136)
        self.assertEqual(workout.heart_rate.values, [0, 80, 81, 82, 0, 0])
        self.assertEqual(workout.heart_rate.trimmed_values, [0, 80, 81, 82])
        self.assertTrue(workout.heart_rate.complete)
        self.assertEqual(workout.heart_rate.next_offsets, [3, 65535])

    def _write_capture(self, path: Path, payloads: list[str]) -> None:
        capture = {
            "schema": "dafit-open.capture.v1",
            "notifications": [
                {
                    "frame": {
                        "command": 0xB2,
                        "payload_hex": payload,
                    }
                }
                for payload in payloads
            ],
        }
        path.write_text(json.dumps(capture))


if __name__ == "__main__":
    unittest.main()

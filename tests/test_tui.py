import unittest

from dafit_open.capture_export import SeriesData, WorkoutSummary
from dafit_open.tui import app_summary_lines, workout_detail_lines, workout_table_rows


class TuiFormattingTest(unittest.TestCase):
    def test_formats_workout_table_rows(self) -> None:
        workout = WorkoutSummary(
            id=11,
            start="2026-02-19T23:49:19+00:00",
            valid_time=2862,
            steps=2729,
            distance=2265,
            calories=136,
            heart_rate=SeriesData(values=[0, 80, 81, 0], chunks=1, complete=True),
        )

        rows = workout_table_rows([workout])

        self.assertEqual(rows[0], "ID   Start               Time    Steps   Dist   Cal   HR       Done")
        self.assertIn(" 11  2026-02-19 23:49", rows[2])
        self.assertIn("47m42s", rows[2])
        self.assertIn("2729", rows[2])
        self.assertIn("2.27", rows[2])
        self.assertIn("2/3", rows[2])
        self.assertTrue(rows[2].endswith("yes"))

    def test_formats_detail_lines(self) -> None:
        workout = WorkoutSummary(
            id=14,
            start="2026-04-12T22:59:11+00:00",
            end="2026-04-13T00:51:23+00:00",
            valid_time=6732,
            steps=4542,
            distance=3769,
            calories=265,
            heart_rate=SeriesData(values=[80, 81], chunks=1, complete=True),
            sources=["ble-logs/fireboltt148-sync-training.json"],
        )

        lines = workout_detail_lines(workout)

        self.assertIn("Workout 14", lines)
        self.assertIn("Valid time   : 1h52m (6732s)", lines)
        self.assertIn("Distance     : 3.77 km (3769 m)", lines)
        self.assertIn("Heart rate   : 2 trimmed, 2 nonzero, 1 chunk(s), complete=True", lines)

    def test_formats_app_summary_lines(self) -> None:
        state = {
            "device": {
                "name": "FireBoltt 148",
                "address": "D3:05:F5:F9:B3:E5",
                "fields": {"battery_level": 56},
            },
            "watch_faces": {
                "display_slot": 8,
                "slots": [
                    {"index": 0, "type": "A", "id": 1},
                    {"index": 1, "type": "B", "id": 3299},
                    {"index": 7, "type": "C", "id": 19719},
                ],
                "support": {"display_index": 19719, "supported": [64]},
            },
            "settings": {"basic": {"goal_steps": 10000}, "daily": {"quick_view": True}},
            "alarms": {"alarms": [{"enabled": True}, {"enabled": False}]},
            "workouts": [{"id": 11}, {"id": 12}],
        }

        lines = app_summary_lines(state)

        self.assertIn("Name         : FireBoltt 148", lines)
        self.assertIn("Battery      : 56%", lines)
        self.assertIn("Slots        : 3 (A:1, B:1, C:1)", lines)
        self.assertIn("Support      : display=19719, supported=64", lines)
        self.assertIn("Settings     : 2 value(s)", lines)
        self.assertIn("Alarms       : 2 total, 1 enabled", lines)
        self.assertIn("Workouts     : 2", lines)


if __name__ == "__main__":
    unittest.main()

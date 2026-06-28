import unittest

from dafit_open.capture_export import SeriesData, WorkoutSummary
from dafit_open.tui import workout_detail_lines, workout_table_rows


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


if __name__ == "__main__":
    unittest.main()

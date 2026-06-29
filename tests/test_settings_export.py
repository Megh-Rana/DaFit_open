import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.settings_export import load_settings_state


class SettingsExportTest(unittest.TestCase):
    def test_loads_settings_from_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            capture = {
                "notifications": [
                    {"frame": {"command": 0x26, "payload_hex": "10 27 00 00"}},
                    {"frame": {"command": 0x27, "payload_hex": "01"}},
                    {"frame": {"command": 0x28, "payload_hex": "01"}},
                    {"frame": {"command": 0x81, "payload_hex": "16 1E 07 00"}},
                    {"frame": {"command": 0x24, "payload_hex": "01"}},
                    {"frame": {"command": 0x2A, "payload_hex": "00"}},
                    {"frame": {"command": 0x2D, "payload_hex": "01"}},
                    {"frame": {"command": 0x82, "payload_hex": "08 00 16 00"}},
                    {"frame": {"command": 0x83, "payload_hex": "3C 32 09 18"}},
                    {"frame": {"command": 0x87, "payload_hex": "01 01 09 00 08 3C"}},
                    {"frame": {"command": 0x87, "payload_hex": "03 00 10 00 06 78"}},
                    {"frame": {"command": 0x8D, "payload_hex": "05"}},
                    {"frame": {"command": 0xAC, "payload_hex": "01"}},
                    {"frame": {"command": 0xBB, "payload_hex": "0C 00 01"}},
                    {"frame": {"command": 0xBB, "payload_hex": "0C 02 08 00 16 00"}},
                    {"frame": {"command": 0xBB, "payload_hex": "04 06 00 01 09 00 08 3C"}},
                ]
            }
            path.write_text(json.dumps(capture))

            state = load_settings_state([path])

        self.assertEqual(state["goal_steps"], 10000)
        self.assertEqual(state["time_system"], 1)
        self.assertTrue(state["display_time_enabled"])
        self.assertTrue(state["quick_view_enabled"])
        self.assertEqual(state["dominant_hand"], 1)
        self.assertEqual(state["metric_system"], 0)
        self.assertEqual(state["display_time"], 5)
        self.assertTrue(state["tap_to_wake_enabled"])
        self.assertEqual(
            state["do_not_disturb"],
            {"start_hour": 22, "start_minute": 30, "end_hour": 7, "end_minute": 0},
        )
        self.assertEqual(
            state["quick_view_time"],
            {"start_hour": 8, "start_minute": 0, "end_hour": 22, "end_minute": 0},
        )
        self.assertEqual(
            state["sedentary_reminder_period"],
            {"period": 60, "steps": 50, "start_hour": 9, "end_hour": 24},
        )
        self.assertEqual(
            state["drink_water_reminder"],
            {"enabled": True, "start_hour": 9, "start_minute": 0, "count": 8, "period": 60},
        )
        self.assertEqual(
            state["hand_washing_reminder"],
            {"enabled": False, "start_hour": 16, "start_minute": 0, "count": 6, "period": 120},
        )
        self.assertTrue(state["screen_off_clock_enabled"])
        self.assertEqual(
            state["screen_off_clock_time"],
            {"start_hour": 8, "start_minute": 0, "end_hour": 22, "end_minute": 0},
        )
        self.assertEqual(
            state["new_drink_water_reminder"],
            {"enabled": True, "start_hour": 9, "start_minute": 0, "count": 8, "period": 60},
        )


if __name__ == "__main__":
    unittest.main()

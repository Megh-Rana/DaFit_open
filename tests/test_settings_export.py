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
                ]
            }
            path.write_text(json.dumps(capture))

            state = load_settings_state([path])

        self.assertEqual(state["goal_steps"], 10000)
        self.assertEqual(state["time_system"], 1)
        self.assertTrue(state["display_time_enabled"])
        self.assertEqual(
            state["do_not_disturb"],
            {"start_hour": 22, "start_minute": 30, "end_hour": 7, "end_minute": 0},
        )


if __name__ == "__main__":
    unittest.main()

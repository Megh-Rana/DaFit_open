import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.alarm_export import load_alarm_state


class AlarmExportTest(unittest.TestCase):
    def test_loads_alarm_state_from_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alarms.json"
            capture = {
                "notifications": [
                    {"frame": {"command": 0x21, "payload_hex": "00 01 02 07 1E 00 00 3E"}},
                    {"frame": {"command": 0xB9, "payload_hex": "15 04 01 03 01 01 08 00 00 00 7F"}},
                ]
            }
            path.write_text(json.dumps(capture))

            state = load_alarm_state([path])

        self.assertEqual(len(state["legacy_alarms"]), 1)
        self.assertEqual(state["legacy_alarms"][0]["hour"], 7)
        self.assertEqual(state["legacy_alarms"][0]["minute"], 30)
        self.assertEqual(state["legacy_alarms"][0]["repeat_mode"], 0x3E)
        self.assertEqual(len(state["new_alarms"]), 1)
        self.assertEqual(state["new_alarms"][0]["id"], 3)
        self.assertEqual(state["new_alarms"][0]["repeat_mode"], 127)


if __name__ == "__main__":
    unittest.main()

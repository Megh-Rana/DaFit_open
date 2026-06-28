import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.watchface_export import load_watch_face_state


class WatchFaceExportTest(unittest.TestCase):
    def test_loads_watch_face_state_from_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watch-faces.json"
            capture = {
                "schema": "dafit-open.capture.v1",
                "notifications": [
                    self._notification(0x2E, "01"),
                    self._notification(0x29, "04"),
                    self._notification(
                        0xA6,
                        "01 02 00 41 00 01 01 42 0C E3",
                    ),
                    self._notification(0x84, "FF FF 40"),
                    self._notification(0xB4, "14 F0 00 F0 00 10 00 50 00 50 00 08 00"),
                ],
            }
            path.write_text(json.dumps(capture))

            state = load_watch_face_state([path])

        self.assertEqual(state["device_version"], 1)
        self.assertEqual(state["display_slot"], 4)
        self.assertEqual(
            state["slots"],
            [
                {"index": 0, "kind": "A", "watch_face_id": 1},
                {"index": 1, "kind": "B", "watch_face_id": 3299},
            ],
        )
        self.assertEqual(state["support"], {"display_index": 65535, "supported": [64]})
        self.assertEqual(state["screen"]["width"], 240)
        self.assertEqual(state["screen"]["thumb_corner"], 8)

    def _notification(self, command: int, payload_hex: str) -> dict:
        return {
            "frame": {
                "command": command,
                "payload_hex": payload_hex,
            }
        }


if __name__ == "__main__":
    unittest.main()

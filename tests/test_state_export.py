import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.state_export import load_app_state


class StateExportTest(unittest.TestCase):
    def test_loads_app_state_from_capture_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write_device_info(directory / "device.json")
            self._write_protocol_capture(directory / "protocol.json")

            state = load_app_state([directory])

        self.assertEqual(state["schema"], "dafit-open.app-state.v1")
        self.assertEqual(state["alarms"]["legacy_alarms"][0]["hour"], 7)
        self.assertEqual(state["device"]["address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(state["device"]["name"], "FireBoltt 148")
        self.assertEqual(state["device"]["fields"]["battery_level"], 76)
        self.assertEqual(state["settings"]["goal_steps"], 10000)
        self.assertEqual(state["watch_faces"]["display_slot"], 4)
        self.assertEqual(state["watch_faces"]["slots"][0]["watch_face_id"], 1)
        self.assertEqual(state["workouts"][0]["id"], 11)

    def _write_device_info(self, path: Path) -> None:
        capture = {
            "address": "AA:BB:CC:DD:EE:FF",
            "device": {"address": "AA:BB:CC:DD:EE:FF", "name": "FireBoltt 148"},
            "services": [{"uuid": "0000180f-0000-1000-8000-00805f9b34fb"}],
            "reads": [
                self._read("00002a00-0000-1000-8000-00805f9b34fb", "Device Name", "FireBoltt 148"),
                self._read("00002a19-0000-1000-8000-00805f9b34fb", "Battery Level", 76),
            ],
        }
        path.write_text(json.dumps(capture))

    def _write_protocol_capture(self, path: Path) -> None:
        capture = {
            "notifications": [
                {"frame": {"command": 0x29, "payload_hex": "04"}},
                {"frame": {"command": 0xA6, "payload_hex": "01 01 00 41 00 01"}},
                {"frame": {"command": 0x26, "payload_hex": "10 27 00 00"}},
                {"frame": {"command": 0x21, "payload_hex": "00 01 02 07 1E 00 00 3E"}},
                {
                    "frame": {
                        "command": 0xB2,
                        "payload_hex": (
                            "03 0B 7F A1 97 69 AD AC 97 69 2E 0B 00 00 "
                            "A9 0A 00 00 D9 08 00 00 88 00 56 00 00 00 48 00"
                        ),
                    }
                },
            ]
        }
        path.write_text(json.dumps(capture))

    def _read(self, uuid: str, name: str, value: object) -> dict:
        return {
            "ok": True,
            "characteristic": {"uuid": uuid, "name": name},
            "value": {"type": "test", "value": value, "hex": ""},
        }


if __name__ == "__main__":
    unittest.main()

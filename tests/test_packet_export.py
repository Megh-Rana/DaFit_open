import json
from pathlib import Path
import tempfile
import unittest

from dafit_open.packet_export import load_packet_events, write_packet_events


class PacketExportTest(unittest.TestCase):
    def test_loads_native_capture_packet_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.json"
            path.write_text(
                json.dumps(
                    {
                        "sent_packets": [
                            {
                                "timestamp": "2026-06-29T10:00:00Z",
                                "channel": "command",
                                "command": 0x29,
                                "payload_hex": "",
                                "hex": "FE EA 10 05 29",
                            }
                        ],
                        "notifications": [
                            {
                                "timestamp": "2026-06-29T10:00:01Z",
                                "characteristic": {"uuid": "0000fee3"},
                                "frame": {
                                    "command": 0x29,
                                    "payload_hex": "05",
                                    "hex": "FE EA 20 06 29 05",
                                },
                            }
                        ],
                    }
                )
            )

            events = load_packet_events([path])

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["direction"], "tx")
        self.assertEqual(events[0]["command_hex"], "0x29")
        self.assertEqual(events[1]["direction"], "rx")
        self.assertEqual(events[1]["decoded"], "display_watch_face=5")

    def test_prefers_fresh_decode_over_stored_notification_decode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.json"
            path.write_text(
                json.dumps(
                    {
                        "notifications": [
                            {
                                "timestamp": "2026-06-29T10:00:00Z",
                                "frame": {
                                    "command": 0x6E,
                                    "payload_hex": "00 01",
                                    "hex": "FE EA 20 07 6E 00 01",
                                    "decoded": "watch_face_background_transfer payload=00 01",
                                },
                            }
                        ],
                    }
                )
            )

            events = load_packet_events([path])

        self.assertEqual(events[0]["decoded"], "watch_face_background_chunk_index index=1")

    def test_loads_imported_app_log_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app-log.json"
            path.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "timestamp": "2026-06-29T10:00:00Z",
                                "kind": "tx_message",
                                "data_hex": "FE EA 10 05 2E",
                                "frame": {
                                    "command": 0x2E,
                                    "payload_hex": "",
                                },
                            }
                        ]
                    }
                )
            )

            events = load_packet_events([path])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "tx_message")
        self.assertEqual(events[0]["direction"], "tx")
        self.assertEqual(events[0]["command"], 0x2E)

    def test_writes_packet_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "packets.csv"
            write_packet_events(
                [
                    {
                        "source": "capture.json",
                        "order": 1,
                        "timestamp": None,
                        "direction": "tx",
                        "kind": "sent_packet",
                        "channel": "command",
                        "command": 0x29,
                        "command_hex": "0x29",
                        "payload_len": 0,
                        "payload_hex": "",
                        "frame_hex": "FE EA 10 05 29",
                        "decoded": "display_watch_face=5",
                    }
                ],
                "csv",
                output=output,
            )

            text = output.read_text()

        self.assertIn("source,order,timestamp,direction", text)
        self.assertIn("capture.json,1,,tx", text)


if __name__ == "__main__":
    unittest.main()

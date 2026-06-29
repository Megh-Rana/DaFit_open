import tempfile
from pathlib import Path
import unittest

from dafit_open.watchface_store import (
    DEFAULT_STORE_PACKET_LENGTH,
    analyze_store_watch_face_bin,
    inspect_store_watch_face_bin,
    plan_store_watch_face_transfer,
)


class WatchFaceStoreTest(unittest.TestCase):
    def test_inspects_and_plans_store_bin_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face.bin"
            path.write_bytes(bytes(range(255)) + b"tail")

            info = inspect_store_watch_face_bin(path)
            plan = plan_store_watch_face_transfer(path, chunk_preview_count=2)

            self.assertEqual(info["schema"], "dafit-open.store-watch-face-bin.v1")
            self.assertEqual(info["size"], 259)
            self.assertEqual(info["default_packet_length"], DEFAULT_STORE_PACKET_LENGTH)
            self.assertEqual(info["default_chunk_count"], 2)
            self.assertEqual(plan.size, 259)
            self.assertEqual(plan.packet_length, DEFAULT_STORE_PACKET_LENGTH)
            self.assertEqual(plan.chunk_count, 2)
            self.assertEqual(
                plan.prepare_packet.build(),
                bytes.fromhex("FE EA 10 09 74 00 00 01 03"),
            )
            self.assertEqual(plan.chunks[0]["index"], 0)
            self.assertEqual(plan.chunks[0]["data_len"], DEFAULT_STORE_PACKET_LENGTH)
            self.assertEqual(plan.chunks[1]["index"], 1)
            self.assertEqual(plan.chunks[1]["data_len"], 15)

    def test_analyzes_store_bin_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face.bin"
            pointer_run = b"".join(value.to_bytes(4, "little") for value in range(64, 128, 8))
            path.write_bytes(
                b"\xAA\xBB"
                + (466).to_bytes(2, "big")
                + b"\x00" * 40
                + pointer_run
                + b"\x55" * 128
            )

            analysis = analyze_store_watch_face_bin(path)

            self.assertEqual(analysis["schema"], "dafit-open.store-watch-face-bin-analysis.v1")
            self.assertTrue(
                any(hit["label"] == "screen_width_466" for hit in analysis["value_hits"])
            )
            self.assertTrue(analysis["zero_runs"])
            self.assertTrue(analysis["monotonic_u32_runs"])


if __name__ == "__main__":
    unittest.main()

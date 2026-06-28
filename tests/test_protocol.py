import unittest

from dafit_open.protocol import (
    decode_frame,
    parse_frame,
    query_training_detail_packet,
    query_training_series_packet,
)


class ProtocolDecodeTest(unittest.TestCase):
    def test_decodes_training_history_list(self) -> None:
        raw = bytes.fromhex(
            "FE EA 20 51 B2 "
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
            "7F A1 97 69 00 "
            "48 2F D8 69 00 "
            "B4 CE D8 69 00 "
            "BF 23 DC 69 00"
        )
        frame = parse_frame(raw)

        self.assertIsNotNone(frame)
        self.assertEqual(
            decode_frame(frame),
            "history_training_list records=["
            "'id=11 type=0 start=2026-02-19T23:49:19+00:00', "
            "'id=12 type=0 start=2026-04-09T22:59:20+00:00', "
            "'id=13 type=0 start=2026-04-10T10:19:32+00:00', "
            "'id=14 type=0 start=2026-04-12T22:59:11+00:00'"
            "]",
        )

    def test_builds_training_detail_query(self) -> None:
        self.assertEqual(
            query_training_detail_packet(11).build(),
            bytes.fromhex("FE EA 10 07 B2 02 0B"),
        )

    def test_decodes_training_detail(self) -> None:
        raw = bytes.fromhex(
            "FE EA 20 23 B2 "
            "03 0B 7F A1 97 69 AD AC 97 69 2E 0B 00 00 "
            "A9 0A 00 00 D9 08 00 00 88 00 56 00 00 00 48 00"
        )
        frame = parse_frame(raw)

        self.assertIsNotNone(frame)
        self.assertEqual(
            decode_frame(frame),
            "history_training_detail id=11 type=0 "
            "start=2026-02-19T23:49:19+00:00 "
            "end=2026-02-20T00:37:01+00:00 "
            "valid_time=2862 steps=2729 distance=2265 calories=136 "
            "payload=03 0B 7F A1 97 69 AD AC 97 69 2E 0B 00 00 "
            "A9 0A 00 00 D9 08 00 00 88 00 56 00 00 00 48 00",
        )

    def test_decodes_training_series_chunks(self) -> None:
        heart_rate = parse_frame(bytes.fromhex("FE EA 20 0A B2 05 0B FF FF 50"))
        distance = parse_frame(bytes.fromhex("FE EA 20 0B B2 0A 0B 00 14 34 12"))

        self.assertIsNotNone(heart_rate)
        self.assertEqual(
            decode_frame(heart_rate),
            "history_training_heart_rate id=11 next_offset=65535 complete=True "
            "count=1 nonzero_count=1 trimmed_count=1 values=[80] payload=05 0B FF FF 50",
        )
        self.assertIsNotNone(distance)
        self.assertEqual(
            decode_frame(distance),
            "history_training_distance id=11 next_offset=20 complete=False "
            "count=1 nonzero_count=1 trimmed_count=1 values=[4660] payload=0A 0B 00 14 34 12",
        )

    def test_builds_training_series_queries(self) -> None:
        self.assertEqual(
            query_training_series_packet(11, "heart-rate").build(),
            bytes.fromhex("FE EA 10 09 B2 04 0B 00 00"),
        )
        self.assertEqual(
            query_training_series_packet(11, "steps", 20).build(),
            bytes.fromhex("FE EA 10 09 B2 07 0B 00 14"),
        )
        self.assertEqual(
            query_training_series_packet(11, "distance", 20).build(),
            bytes.fromhex("FE EA 10 09 B2 09 0B 00 14"),
        )


if __name__ == "__main__":
    unittest.main()

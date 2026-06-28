import unittest

from dafit_open.protocol import decode_frame, parse_frame, query_training_detail_packet


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


if __name__ == "__main__":
    unittest.main()

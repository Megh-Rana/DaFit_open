import unittest

from dafit_open.protocol import (
    decode_frame,
    parse_frame,
    parse_alarm_list,
    parse_display_watch_face,
    parse_new_alarm_list,
    parse_support_watch_faces,
    parse_watch_face_screen,
    query_training_detail_packet,
    query_training_series_packet,
    set_current_time_packet,
    set_do_not_disturb_time_packet,
    set_goal_steps_packet,
    set_time_system_packet,
    set_timezone_packet,
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

    def test_parses_watch_face_state_payloads(self) -> None:
        self.assertEqual(parse_display_watch_face(bytes.fromhex("06")), 6)

        support = parse_support_watch_faces(bytes.fromhex("FF FF 40"))
        self.assertIsNotNone(support)
        self.assertEqual(support.display_index, 65535)
        self.assertEqual(support.supported, [64])

        screen = parse_watch_face_screen(bytes.fromhex("14 F0 00 F0 00 10 00 50 00 50 00 08 00"))
        self.assertIsNotNone(screen)
        self.assertEqual(screen.width, 240)
        self.assertEqual(screen.height, 240)
        self.assertEqual(screen.corner, 16)
        self.assertEqual(screen.thumb_width, 80)
        self.assertEqual(screen.thumb_height, 80)
        self.assertEqual(screen.thumb_corner, 8)

    def test_builds_settings_packets(self) -> None:
        self.assertEqual(
            set_goal_steps_packet(10000).build(),
            bytes.fromhex("FE EA 10 09 16 00 00 27 10"),
        )
        self.assertEqual(set_time_system_packet(1).build(), bytes.fromhex("FE EA 10 06 17 01"))
        self.assertEqual(
            set_do_not_disturb_time_packet(22, 30, 7, 0).build(),
            bytes.fromhex("FE EA 10 09 71 16 1E 07 00"),
        )
        self.assertEqual(
            set_current_time_packet(0x12345678).build(),
            bytes.fromhex("FE EA 10 0A 31 12 34 56 78 08"),
        )
        self.assertEqual(
            set_timezone_packet(19800).build(),
            bytes.fromhex("FE EA 10 0B BB 07 00 58 4D 00 00"),
        )

    def test_decodes_settings_frames(self) -> None:
        self.assertEqual(decode_frame(parse_frame(bytes.fromhex("FE EA 20 06 27 01"))), "time_system=1 payload=01")
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 81 16 1E 07 00"))),
            "do_not_disturb_time start=22:30 end=07:00 payload=16 1E 07 00",
        )

    def test_parses_alarm_payloads(self) -> None:
        alarms = parse_alarm_list(bytes.fromhex("00 01 02 07 1E 00 00 3E"))

        self.assertIsNotNone(alarms)
        self.assertEqual(alarms[0].id, 0)
        self.assertTrue(alarms[0].enabled)
        self.assertEqual(alarms[0].hour, 7)
        self.assertEqual(alarms[0].minute, 30)
        self.assertEqual(alarms[0].repeat_mode, 0x3E)
        self.assertIsNone(alarms[0].date)

        dated = parse_alarm_list(bytes.fromhex("02 01 00 06 15 B6 1D 00"))
        self.assertIsNotNone(dated)
        self.assertEqual(dated[0].date, "2026-06-29")

        new_alarms = parse_new_alarm_list(bytes.fromhex("15 04 01 03 01 01 08 00 00 00 7F"))
        self.assertIsNotNone(new_alarms)
        self.assertEqual(new_alarms[0].id, 3)
        self.assertEqual(new_alarms[0].repeat_mode, 127)


if __name__ == "__main__":
    unittest.main()

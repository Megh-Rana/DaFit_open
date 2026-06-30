import unittest

from dafit_open.protocol import (
    AlarmInfo,
    QUERY_SETS,
    delete_all_new_alarms_packet,
    delete_new_alarm_packet,
    decode_frame,
    encode_alarm_record,
    file_transfer_abort_packet,
    file_transfer_check_packet,
    parse_frame,
    parse_alarm_list,
    parse_display_watch_face,
    parse_file_transfer_crc,
    parse_file_transfer_offset,
    parse_new_alarm_list,
    parse_package_length,
    parse_store_watch_face_crc,
    parse_store_watch_face_offset,
    parse_support_watch_faces,
    parse_watch_face_screen,
    query_training_detail_packet,
    query_training_series_packet,
    set_current_time_packet,
    set_do_not_disturb_time_packet,
    set_goal_steps_packet,
    set_legacy_alarm_packet,
    set_new_alarm_packet,
    set_time_system_packet,
    set_timezone_packet,
    store_watch_face_check_packet,
    store_watch_face_prepare_packet,
    watch_face_background_check_packet,
    watch_face_background_size_packet,
    watch_face_layout_packet,
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

    def test_decodes_file_transfer_events(self) -> None:
        self.assertEqual(parse_package_length(bytes.fromhex("01 00 01")), 256)
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 08 BA 01 00 01"))),
            "package_length=256",
        )
        self.assertEqual(parse_file_transfer_offset(bytes.fromhex("01 34 12 00 00")), 0x1234)
        self.assertEqual(parse_file_transfer_crc(bytes.fromhex("02 00 00 BA AE")), 0xBAAE)
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0A B7 01 34 12 00 00"))),
            "file_transfer_offset offset=4660",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0A B7 02 00 00 BA AE"))),
            "file_transfer_crc crc=0xBAAE payload=02 00 00 BA AE",
        )
        self.assertEqual(file_transfer_check_packet(True).build(), bytes.fromhex("FE EA 10 06 B7 03"))
        self.assertEqual(file_transfer_check_packet(False).build(), bytes.fromhex("FE EA 10 06 B7 04"))
        self.assertEqual(file_transfer_abort_packet().build(), bytes.fromhex("FE EA 10 06 B7 05"))

    def test_decodes_store_watch_face_transfer_events(self) -> None:
        self.assertEqual(
            store_watch_face_prepare_packet(140356).build(),
            bytes.fromhex("FE EA 10 09 74 00 02 24 44"),
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 74 00 02 24 44"))),
            "store_watch_face_prepare size=140356",
        )
        self.assertEqual(parse_store_watch_face_offset(bytes.fromhex("02 3F")), 575)
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 07 74 02 3F"))),
            "store_watch_face_offset index=575",
        )
        self.assertEqual(parse_store_watch_face_crc(bytes.fromhex("FF FF ED FA")), 0xEDFA)
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 74 FF FF ED FA"))),
            "store_watch_face_crc crc=0xEDFA",
        )
        self.assertEqual(
            store_watch_face_check_packet(True).build(),
            bytes.fromhex("FE EA 10 09 74 00 00 00 00"),
        )

    def test_builds_original_background_transfer_packets(self) -> None:
        self.assertEqual(
            watch_face_background_size_packet(434312).build(),
            bytes.fromhex("FE EA 10 09 6E 00 06 A0 88"),
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 10 09 6E 00 06 A0 88"))),
            "watch_face_background_size size=434312",
        )
        self.assertEqual(
            watch_face_background_check_packet(True).build(),
            bytes.fromhex("FE EA 10 09 6E 00 00 00 00"),
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 10 09 6E FF FF FF FF"))),
            "watch_face_background_check_failed",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0A 6E 01 40 00 00 00"))),
            "watch_face_background_offset offset=64",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 07 6E 00 01"))),
            "watch_face_background_chunk_index index=1",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0A 6E 02 00 00 76 3D"))),
            "watch_face_background_crc crc=0x763D payload=02 00 00 76 3D",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 6E FF FF 00 00"))),
            "watch_face_background_crc crc=0x0000 payload=FF FF 00 00",
        )

    def test_builds_watch_face_layout_packet(self) -> None:
        self.assertEqual(
            watch_face_layout_packet(
                time_position=1,
                time_top_content=2,
                time_bottom_content=3,
                text_color=(255, 255, 255),
                background_md5="00000000000000000000000000000000",
            ).build(),
            bytes.fromhex(
                "FE EA 10 2A 38 01 02 03 FF FF "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
                "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
            ),
        )

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
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 06 28 01"))),
            "quick_view_enabled=True display_time_enabled=True payload=01",
        )

    def test_decodes_daily_settings_frames(self) -> None:
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 06 2D 01"))),
            "sedentary_reminder_enabled=True payload=01",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 82 08 00 16 00"))),
            "quick_view_time start=08:00 end=22:00 payload=08 00 16 00",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 09 83 3C 32 09 18"))),
            "sedentary_reminder_period period=60 steps=50 start_hour=9 end_hour=24 payload=3C 32 09 18",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0B 87 01 01 09 00 08 3C"))),
            "drink_water_reminder enabled=True start=09:00 count=8 period=60 payload=01 01 09 00 08 3C",
        )
        self.assertEqual(
            decode_frame(parse_frame(bytes.fromhex("FE EA 20 0B BB 0C 02 08 00 16 00"))),
            "screen_off_clock_time start=08:00 end=22:00 payload=0C 02 08 00 16 00",
        )

    def test_daily_settings_query_set_contains_read_packets(self) -> None:
        packets = QUERY_SETS["daily-settings"]

        self.assertIn(0x28, [packet.command for packet in packets])
        self.assertIn(0x83, [packet.command for packet in packets])
        self.assertIn(0xBB, [packet.command for packet in packets])

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

    def test_builds_alarm_packets(self) -> None:
        alarm = AlarmInfo(id=3, enabled=True, hour=8, minute=0, repeat_mode=127)

        self.assertEqual(encode_alarm_record(alarm), bytes.fromhex("03 01 01 08 00 00 00 7F"))
        self.assertEqual(
            set_new_alarm_packet(alarm).build(),
            bytes.fromhex("FE EA 10 0F B9 05 00 03 01 01 08 00 00 00 7F"),
        )
        self.assertEqual(
            set_legacy_alarm_packet(alarm).build(),
            bytes.fromhex("FE EA 10 0D 11 03 01 01 08 00 00 00 7F"),
        )
        self.assertEqual(
            delete_new_alarm_packet(3).build(),
            bytes.fromhex("FE EA 10 08 B9 05 02 03"),
        )
        self.assertEqual(
            delete_all_new_alarms_packet().build(),
            bytes.fromhex("FE EA 10 07 B9 05 03"),
        )

    def test_builds_dated_alarm_record(self) -> None:
        alarm = AlarmInfo(
            id=2,
            enabled=True,
            hour=6,
            minute=21,
            repeat_mode=99,
            date="2026-06-29",
        )

        self.assertEqual(encode_alarm_record(alarm), bytes.fromhex("02 01 00 06 15 B6 1D 00"))


if __name__ == "__main__":
    unittest.main()

import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

from dafit_open.watchface_image import (
    PixelImage,
    build_original_background_package,
    build_watch_face_package,
    crp_crc16,
    crp_crc16_wrapped_transfer,
    crp_rgb565,
    inspect_watch_face_package,
    load_image,
    plan_original_background_transfer,
    plan_watch_face_transfer,
    wrap_transfer_chunk,
)


class WatchFaceImageTest(unittest.TestCase):
    def test_loads_ppm_and_encodes_rgb565(self) -> None:
        image = PixelImage(
            width=2,
            height=1,
            pixels=[(255, 0, 0), (0, 255, 0)],
        )

        self.assertEqual(image.to_rgb565("little"), bytes.fromhex("00 F8 E0 07"))
        self.assertEqual(image.to_rgb565("big"), bytes.fromhex("F8 00 07 E0"))
        self.assertEqual(image.to_rgb565("big", color_order="bgr"), bytes.fromhex("00 1F 07 E0"))

    def test_rgb565_matches_crp_marker_quirk(self) -> None:
        self.assertEqual(crp_rgb565(8, 4, 8), 0x0822)
        image = PixelImage(width=1, height=1, pixels=[(8, 4, 8)])

        self.assertEqual(image.to_rgb565("big"), bytes.fromhex("08 22"))

    def test_builds_watch_face_package_and_transfer_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(
                b"P6\n2 2\n255\n"
                + bytes(
                    [
                        255,
                        0,
                        0,
                        0,
                        255,
                        0,
                        0,
                        0,
                        255,
                        255,
                        255,
                        255,
                    ]
                )
            )
            package = directory / "package"

            manifest = build_watch_face_package(
                source,
                package,
                width=2,
                height=2,
                thumb_width=1,
                thumb_height=1,
            )
            inspection = inspect_watch_face_package(package)
            plan = plan_watch_face_transfer(package, transfer_type=14, packet_length=4)

            self.assertEqual(manifest["schema"], "dafit-open.watch-face-package.v1")
            self.assertEqual((package / "face.rgb565").read_bytes(), bytes.fromhex("00 F8 E0 07 1F 00 FF FF"))
            self.assertTrue((package / "preview.ppm").exists())
            self.assertTrue(inspection["valid"])
            self.assertEqual(inspection["transferable_size"], 10)
            self.assertEqual(plan.prepare_packet.build(), bytes.fromhex("FE EA 10 0B B4 01 0A 00 00 00 02"))
            self.assertEqual(plan.files[0]["crc16"], "0xBAAE")
            self.assertEqual(plan.files[0]["chunk_count"], 2)
            self.assertEqual(
                plan.start_packets[0][1].build(),
                bytes.fromhex("FE EA 10 16 B7 00 0E 08 00 00 00 66 61 63 65 2E 72 67 62 35 36 35"),
            )
            self.assertEqual(plan.chunks[0]["frame_hex"], "FE 70 41 04 00 F8 E0 07")
            saved_manifest = json.loads((package / "manifest.json").read_text())
            self.assertEqual(saved_manifest["files"][0]["size"], 8)

            (package / "face.rgb565").write_bytes(b"tampered")
            tampered = inspect_watch_face_package(package)
            self.assertFalse(tampered["valid"])
            self.assertFalse(tampered["files"][0]["sha256_ok"])

    def test_transfer_plan_can_use_short_role_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(b"P6\n1 1\n255\n" + bytes([255, 0, 0]))
            package = directory / "package"
            build_watch_face_package(source, package, width=1, height=1, thumb_width=1, thumb_height=1)

            plan = plan_watch_face_transfer(package, transfer_type=14, name_mode="role")

            self.assertEqual(plan.files[0]["transfer_name"], "face.bin")
            self.assertEqual(plan.files[1]["transfer_name"], "thumb.bin")
            self.assertEqual(
                plan.start_packets[0][1].build(),
                bytes.fromhex("FE EA 10 13 B7 00 0E 02 00 00 00 66 61 63 65 2E 62 69 6E"),
            )

    def test_builds_original_background_package_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(b"P6\n2 1\n255\n" + bytes([255, 0, 0, 0, 255, 0]))
            package = directory / "original"

            manifest = build_original_background_package(source, package, width=2, height=1)
            plan = plan_original_background_transfer(package, packet_length=4)

            self.assertEqual(manifest["schema"], "dafit-open.original-background-package.v1")
            self.assertEqual((package / "background.rgb565").read_bytes(), bytes.fromhex("F8 00 07 E0"))
            self.assertEqual(manifest["color_order"], "rgb")
            self.assertEqual(manifest["scan_order"], "top-down")
            self.assertEqual(plan.payload_size, 4)
            self.assertEqual(plan.chunk_count, 1)
            self.assertEqual(plan.last_chunk_size, 4)
            self.assertEqual(plan.wrapped_transfer_size, 8)
            self.assertEqual(plan.wrapper_overhead_size, 4)
            self.assertEqual(plan.wrapped_transfer_crc16, crp_crc16(bytes.fromhex("FE 24 D0 04 F8 00 07 E0")))
            self.assertEqual(plan.announced_size, 8)
            self.assertEqual(
                plan.size_packet.build(),
                bytes.fromhex("FE EA 10 09 6E 00 00 00 08"),
            )
            self.assertEqual(plan.chunks[0]["frame_hex"], "FE 24 D0 04 F8 00 07 E0")

    def test_original_background_pixel_order_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(b"P6\n1 2\n255\n" + bytes([255, 0, 0, 0, 0, 255]))
            package = directory / "original"

            manifest = build_original_background_package(
                source,
                package,
                width=1,
                height=2,
                byteorder="big",
                color_order="bgr",
                scan_order="bottom-up",
            )

            self.assertEqual(manifest["color_order"], "bgr")
            self.assertEqual(manifest["scan_order"], "bottom-up")
            self.assertEqual((package / "background.rgb565").read_bytes(), bytes.fromhex("F8 00 00 1F"))

    def test_original_background_announces_wrapped_transfer_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(b"P6\n2 2\n255\n" + bytes([255, 0, 0] * 4))
            package = directory / "original"

            build_original_background_package(source, package, width=2, height=2)
            plan = plan_original_background_transfer(package, packet_length=3)

            self.assertEqual(plan.payload_size, 8)
            self.assertEqual(plan.chunk_count, 3)
            self.assertEqual(plan.wrapper_overhead_size, 12)
            self.assertEqual(plan.wrapped_transfer_size, 20)
            self.assertEqual(plan.wrapped_transfer_crc16, crp_crc16_wrapped_transfer((package / "background.rgb565").read_bytes(), 3))
            self.assertEqual(plan.announced_size, 20)
            self.assertEqual(
                plan.size_packet.build(),
                bytes.fromhex("FE EA 10 09 6E 00 00 00 14"),
            )

    def test_original_background_fit_and_circular_mask_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ppm"
            source.write_bytes(
                b"P6\n2 1\n255\n"
                + bytes(
                    [
                        255,
                        0,
                        0,
                        0,
                        255,
                        0,
                    ]
                )
            )
            package = directory / "original"

            manifest = build_original_background_package(
                source,
                package,
                width=4,
                height=4,
                fit="contain",
                circular_mask=True,
            )
            payload = (package / "background.rgb565").read_bytes()

            self.assertEqual(manifest["fit"], "contain")
            self.assertTrue(manifest["circular_mask"])
            self.assertEqual(manifest["payload_size"], 32)
            self.assertEqual(len(payload), 32)
            self.assertEqual(payload[:2], bytes.fromhex("00 00"))
            self.assertNotEqual(payload[10:12], bytes.fromhex("00 00"))

    def test_wraps_transfer_chunks(self) -> None:
        data = bytes.fromhex("00 F8 E0 07")

        self.assertEqual(crp_crc16(data), 0x7041)
        self.assertEqual(wrap_transfer_chunk(data, 256), bytes.fromhex("FE 70 41 04 00 F8 E0 07"))
        self.assertEqual(wrap_transfer_chunk(data, 64), bytes.fromhex("FF FF 70 41 04 00 F8 E0 07"))
        self.assertEqual(
            crp_crc16_wrapped_transfer(data, 256),
            crp_crc16(bytes.fromhex("FE 70 41 04 00 F8 E0 07")),
        )

    def test_load_image_reports_pillow_requirement_for_png_without_pillow(self) -> None:
        if importlib.util.find_spec("PIL") is not None:
            self.skipTest("Pillow is installed")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            path.write_bytes(b"not really png")

            try:
                load_image(path)
            except RuntimeError as exc:
                self.assertIn("requires Pillow", str(exc))


if __name__ == "__main__":
    unittest.main()

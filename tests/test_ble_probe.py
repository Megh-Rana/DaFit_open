import unittest

from dafit_open.ble_probe import _original_background_fallback_packet_length


class BleProbeTest(unittest.TestCase):
    def test_original_background_fallback_uses_single_write_payload(self) -> None:
        self.assertEqual(_original_background_fallback_packet_length(244), 240)
        self.assertEqual(_original_background_fallback_packet_length(100), 96)
        self.assertEqual(_original_background_fallback_packet_length(5), 1)
        self.assertEqual(_original_background_fallback_packet_length(4), 1)


if __name__ == "__main__":
    unittest.main()

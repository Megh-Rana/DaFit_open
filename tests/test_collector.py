import unittest

from dafit_open.collector import default_collection_dir


class CollectorTest(unittest.TestCase):
    def test_default_collection_dir_uses_safe_address(self) -> None:
        path = default_collection_dir("AA:BB:CC:DD:EE:FF")

        self.assertEqual(path.parts[0], "ble-logs")
        self.assertTrue(path.name.startswith("collect-aabbccddeeff-"))
        self.assertTrue(path.name.endswith("Z"))


if __name__ == "__main__":
    unittest.main()

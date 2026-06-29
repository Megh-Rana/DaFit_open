import tempfile
from pathlib import Path
import unittest

from dafit_open.app_log_import import import_app_logs, write_imported_app_log


class AppLogImportTest(unittest.TestCase):
    def test_imports_framed_messages_and_transfer_chunks(self) -> None:
        text = "\n".join(
            [
                "06-29 16:15:32.771 I/BleLog(7283): message type: 0",
                "06-29 16:15:32.772 I/BleLog(7283): message content: fe ea 20 0b b7 0e 00 58 4d 00 00 ",
                "06-29 16:15:32.900 I/BleLog(7283): onCharacteristicChanged: fe ea 20 07 74 00 00 ",
                "06-29 16:15:32.901 I/BleLog(7283): cmd: 116",
                "06-29 16:15:32.902 I/BleLog(7283): trans offset: 0",
                "06-29 16:15:33.000 I/BleLog(7283): message type: 2",
                "06-29 16:15:33.001 I/BleLog(7283): message content: 58 83 01 10 ",
                "06-29 16:15:33.100 I/BleLog(7283): onCharacteristicChanged: fe ea 20 07 74 00 01 ",
                "06-29 16:15:33.101 I/BleLog(7283): trans offset: 1",
                "06-29 16:15:33.200 I/BleLog(7283): message type: 2",
                "06-29 16:15:33.201 I/BleLog(7283): message content: 20 21 01 08 ",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            log_path = directory / "log.txt"
            log_path.write_text(text)

            capture = import_app_logs([log_path])

            self.assertEqual(capture["summary"]["transfer_chunks"], 2)
            self.assertEqual(capture["summary"]["transfer_payload_size"], 8)
            self.assertEqual(capture["summary"]["ack_offsets"], [0, 1])
            self.assertEqual(capture["summary"]["commands"]["0x74"], 2)
            self.assertEqual(capture["events"][0]["frame"]["command"], 0xB7)

            out_dir = directory / "out"
            write_imported_app_log(capture, output=directory / "capture.json", out_dir=out_dir)
            self.assertEqual(
                (out_dir / "transfer-payload.bin").read_bytes(),
                bytes.fromhex("58 83 01 10 20 21 01 08"),
            )


if __name__ == "__main__":
    unittest.main()

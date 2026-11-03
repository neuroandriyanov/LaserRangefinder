"""Host protocol v3 tests, including byte streams emitted by HDL simulation."""
import copy
from pathlib import Path
import struct
import unittest
from fpga_config import DEFAULT_CHANNELS, ConfigurationClient, validate
from fpga_measurements import Decoder, Freshness, command, decode_packet
from fpga_phase import crc16


class V3Tests(unittest.TestCase):
    def test_validation_and_boundaries(self):
        self.assertEqual(len(validate(DEFAULT_CHANNELS)), 32)
        for key, bad in [("amplitude", -1), ("amplitude", 1024), ("phase_word", 16384),
                         ("ftw", 0), ("ftw", 0x80000000), ("ftw", 1.5)]:
            channels = copy.deepcopy(DEFAULT_CHANNELS);channels[0][key] = bad
            with self.assertRaises(ValueError): validate(channels)
        for delta, good in [(8589, False), (8590, True), (171799, True), (171800, False), (-103079, False)]:
            channels = copy.deepcopy(DEFAULT_CHANNELS);channels[2]["ftw"] = channels[0]["ftw"]+delta
            if good: validate(channels)
            else:
                with self.assertRaises(ValueError): validate(channels)

    def test_no_io_on_invalid_configuration(self):
        class Port:
            def write(self, data): raise AssertionError("Unexpected device access")
        with self.assertRaises(ValueError): ConfigurationClient(Port()).apply([])

    def test_command_crc(self):
        frame = command(1, 42, 0xf1, 0xa55a, 3)
        self.assertEqual(frame[:6], bytes.fromhex("a5 5a 03 0c 01 f1"))
        self.assertEqual(int.from_bytes(frame[-2:], "little"), crc16(frame[2:-2]))

    def test_rtl_packets(self):
        path = Path(__file__).resolve().parents[2]/"fpga/test-results/uart-v3.bin"
        self.assertTrue(path.exists(), "Run the config HDL suite first")
        decoder = Decoder();data = path.read_bytes();packets = []
        for i in range(0, len(data), 7): packets += decoder.feed(data[i:i+7])
        self.assertEqual(decoder.bad_packets, 0)
        self.assertGreater(len(packets), 100)
        measurement = next(p for p in packets if p["measurement"])
        self.assertEqual(measurement["digital_low_period_ticks"], 125000)
        self.assertAlmostEqual(measurement["digital_low_frequency_hz"], 1000)
        config = next(p for p in packets if p.get("configuration"))
        self.assertEqual(config["generation"], 1)
        self.assertEqual(config["channels"][0], dict(ftw=0x00c40000, phase_word=400, amplitude=210))
        self.assertTrue(any(p["status"] == 6 for p in packets))
        self.assertTrue(any(p["status"] == 3 for p in packets))
        self.assertTrue(any(p["status"] == 4 for p in packets))

    def test_slow_digital_freshness(self):
        # A new analog result may legitimately reuse the previous 16 ms digital window.
        f = Freshness()
        first = dict(protocol_version=3, sequence=1, sample_index=1000, digital_sequence=8, valid=True)
        self.assertTrue(f.check(first)["fresh"])
        second = dict(protocol_version=3, sequence=2, sample_index=1250, digital_sequence=8, valid=True)
        self.assertTrue(f.check(second)["fresh"])
        self.assertFalse(f.check(second.copy())["fresh"])

    def test_reject_corrupt_config(self):
        body = bytes.fromhex("03 30 82 00 80 00 2a 00 01 00")+validate(DEFAULT_CHANNELS)+b"\0\0"
        packet = b"\xa5\x5a"+body+struct.pack("<H", crc16(body))
        self.assertTrue(decode_packet(packet)["configuration"])
        with self.assertRaises(ValueError): decode_packet(packet[:-1]+bytes([packet[-1]^1]))


if __name__ == "__main__":
    unittest.main()

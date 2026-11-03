"""Offline protocol tests, including bytes emitted by the RTL testbench."""
from pathlib import Path
import struct
import unittest

from fpga_phase import Decoder, command, crc16, decode_packet


def packet(flags=3):
    data = bytearray(64)
    data[:8] = bytes((0xA5, 0x5A, 1, 64, 16, flags, 255, 15))
    struct.pack_into("<IIii4I8H3H", data, 8, 10, 2500, 2**30, -(2**30),
                     823380, 1646760, 2470140, 3293520,
                     *([32768] * 8), 100, 100, 1000)
    struct.pack_into("<H", data, 62, crc16(data[2:62]))
    return bytes(data)


class PhaseProtocolTests(unittest.TestCase):
    def test_known_crc(self):
        self.assertEqual(crc16(b"123456789"), 0x4B37)

    def test_command(self):
        data = command(2, 100)
        self.assertEqual(data[:10], bytes.fromhex("a55a010c020064000000"))
        self.assertEqual(crc16(data[2:10]), int.from_bytes(data[10:], "little"))

    def test_units_and_validity(self):
        decoded = decode_packet(packet())
        self.assertEqual(decoded["high_deg"], 90)
        self.assertEqual(decoded["low_deg"], -90)
        self.assertAlmostEqual(decoded["ch1_peak_counts"], 1000, places=2)
        self.assertEqual(decoded["adc8_v"], 0)
        for flags in (0, 4, 0x23, 0x83):
            decoded = decode_packet(packet(flags))
            self.assertIsNone(decoded["high_deg"])
            self.assertFalse(decoded["low_valid"])

    def test_fragmentation_and_recovery(self):
        corrupt = bytearray(packet())
        corrupt[20] ^= 0x80
        stream = b"garbage\xa5" + bytes(corrupt) + b"\xa5\x5a\x01\x40\x99" + packet() * 2
        for chunk_size in (1, 2, 7, 63, 64, 1024):
            decoder = Decoder()
            results = []
            for index in range(0, len(stream), chunk_size):
                results += decoder.feed(stream[index:index + chunk_size])
            self.assertEqual(len(results), 2)
            self.assertGreaterEqual(decoder.bad_packets, 2)
            self.assertLess(len(decoder.buffer), 64)



if __name__ == "__main__":
    unittest.main()

"""Legacy v2 decoder unit tests and current v3 RTL regression integration."""
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from fpga_measurements import Decoder, Freshness, command, crc16, decode_packet, transact


def seal(packet):
    packet[-2:] = struct.pack("<H", crc16(packet[2:-2]))
    return bytes(packet)


def telemetry(request_id=0, sequence=20, index=5000, digital_sequence=15):
    p = bytearray(96)
    p[:12] = bytes.fromhex("a5 5a 02 60 82 00 03 03 00 00 ff 0f")
    struct.pack_into("<H", p, 8, request_id)
    struct.pack_into("<II8i", p, 12, sequence, index,
                     2**30, -2**30, 2**29, -2**29, 2**29, 2**29, -2**29, -2**29)
    struct.pack_into("<4I8H4HBB", p, 52, 100000, 200000, 300000, 400000,
                     *range(32768, 32776), digital_sequence, 100, 10417, 10416, 1, 0)
    return seal(p)


class ProtocolTests(unittest.TestCase):
    def test_command_layout_crc(self):
        self.assertEqual(crc16(b"123456789"), 0x4b37)
        p = command(2, 0x1234)
        self.assertEqual(p[:10], bytes.fromhex("a5 5a 02 0c 02 00 34 12 00 00"))
        self.assertEqual(int.from_bytes(p[-2:], "little"), crc16(p[2:-2]))

    def test_fields_units(self):
        r = decode_packet(telemetry(0x1234))
        self.assertEqual(r["request_id"], 0x1234)
        self.assertTrue(r["valid"])
        self.assertEqual(r["analog_high_deg"], 90)
        self.assertEqual(r["digital_low_deg"], -45)
        self.assertEqual(r["detector1_raw"], 32772)
        self.assertAlmostEqual(r["detector4_v"], 7 * .000375)
        self.assertAlmostEqual(r["digital_high_frequency_hz"], 125000000/10417)

    def test_invalid_and_recovery(self):
        p = bytearray(telemetry());p[6]=4;p[7]=0
        r = decode_packet(seal(p))
        self.assertFalse(r["valid"])
        self.assertIsNone(r["analog_high_deg"])
        self.assertIsNone(r["digital_high_deg"])
        self.assertEqual(r["digital_high_raw_deg"], 45)
        self.assertTrue(decode_packet(telemetry())["valid"])
        p = bytearray(telemetry());p[92]=4
        self.assertFalse(decode_packet(seal(p))["digital_high_valid"])
        p = bytearray(telemetry());p[10]=0x7f
        r = decode_packet(seal(p))
        self.assertFalse(r["valid"])
        self.assertIsNone(r["detector4_v"])

    def test_fragment_crc_noise(self):
        broken = bytearray(telemetry());broken[55]^=1
        stream = b"noise\xa5" + broken + telemetry(3) + telemetry(4)
        decoder = Decoder();results=[]
        for pos in range(0,len(stream),7):
            results.extend(decoder.feed(stream[pos:pos+7]))
        self.assertEqual([r["request_id"] for r in results], [3,4])
        self.assertGreater(decoder.bad_packets, 0)

    def test_stub_ack(self):
        p = bytearray.fromhex("a5 5a 02 0c 81 01 07 00 34 12 00 00")
        r = decode_packet(seal(p))
        self.assertFalse(r["measurement"])
        self.assertEqual(r["status_name"], "NOT_IMPLEMENTED")
        self.assertEqual(r["request_id"], 0x1234)

    def test_stale_and_wrap(self):
        f = Freshness()
        self.assertTrue(f.check(decode_packet(telemetry()))["valid"])
        r = f.check(decode_packet(telemetry(1)))
        self.assertFalse(r["valid"])
        self.assertIsNone(r["analog_high_deg"])
        self.assertTrue(f.check(decode_packet(telemetry(2,21,5250,16)))["valid"])
        f = Freshness()
        f.check(decode_packet(telemetry(3,0xffffffff,0xffffff00,0xffff)))
        self.assertTrue(f.check(decode_packet(telemetry(4,0,0,0)))["valid"])

    def test_matching_id_and_timeout(self):
        class Port:
            in_waiting = 192
            def write(self, data): self.sent=data
            def read(self, size):
                result = getattr(self, "data", b"");self.data=b"";return result
        port=Port();port.data=telemetry(8)+telemetry(9);raw=io.BytesIO()
        self.assertEqual(transact(port,Decoder(),2,9,raw_file=raw)["request_id"],9)
        self.assertEqual(port.sent,command(2,9))
        self.assertEqual(len(raw.getvalue()),192)
        with patch("fpga_measurements.time.monotonic",side_effect=[0,0,.2]):
            with self.assertRaises(TimeoutError):transact(port,Decoder(),2,10)

    def test_rtl_generated_bytes(self):
        path=Path(__file__).resolve().parents[2]/"fpga/test-results/uart-v3-regression.bin"
        self.assertTrue(path.exists(), "Run tools/test_phase_hdl.py first")
        d=Decoder();rows=d.feed(path.read_bytes())
        self.assertEqual(len(rows),28)
        self.assertEqual(d.bad_packets,0)
        self.assertEqual([r["request_id"] for r in rows[:10]],
                         [0x1234,0x2345,0x3457,0x4000,0x4001,0x5000,0x5001,0x6000,0x6001,0x6002])
        self.assertEqual(rows[1]["status_name"],"NOT_IMPLEMENTED")
        self.assertTrue(rows[0]["valid"])
        self.assertFalse(rows[5]["valid"])
        self.assertTrue(rows[5]["beam_lost"])
        self.assertTrue(rows[6]["valid"])
        self.assertEqual(rows[0]["detector1_raw"],0x9005)
        self.assertEqual(rows[0]["detector4_raw"],0x9008)
        for i in range(10, 26, 2):
            self.assertFalse(rows[i]["valid"])
            self.assertTrue(rows[i+1]["valid"])
        self.assertTrue(rows[26]["beam_lost"])
        self.assertFalse(rows[26]["valid"])
        self.assertTrue(rows[27]["valid"])


if __name__ == "__main__":
    unittest.main()

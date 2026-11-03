"""Protocol tests; fixtures are synthetic, not device measurements."""
import unittest
from vector60 import FrameParser, decode_frame


def frame(distance=12345):
    return b'ATD' + distance.to_bytes(4, 'big', signed=True) + b'\x00#'


class ProtocolTests(unittest.TestCase):
    def test_scale_signed_and_unknown_angles(self):
        self.assertEqual(decode_frame(frame())['distance_m'], 1.2345)
        self.assertEqual(decode_frame(frame(-1))['distance_m'], -.0001)
        self.assertIsNone(decode_frame(frame())['angle_x_deg'])

    def test_every_fragment_boundary_and_duplicate(self):
        packet = frame(0x230041)  # '#' and 'A' are valid binary data, not delimiters
        for boundary in range(len(packet) + 1):
            parser = FrameParser()
            values = parser.feed(packet[:boundary]) + parser.feed(packet[boundary:] + packet)
            self.assertEqual(len(values), 2)
            self.assertEqual(values[0], values[1])

    def test_corruption_resynchronizes(self):
        parser = FrameParser()
        self.assertEqual(len(parser.feed(b'noiseATD123456broken' + frame())), 1)
        self.assertEqual(len(parser.buffer), 0)
        for data in [b'', b'ATD', frame()[:-1] + b'x']:
            with self.assertRaises(ValueError):
                decode_frame(data)

    def test_extended_frame(self):
        packet = b'ATD' + (10000).to_bytes(4, 'big') + (-123).to_bytes(4, 'big', signed=True) + (456).to_bytes(4, 'big') + b'\x00#'
        values = FrameParser(17).feed(packet)
        self.assertEqual(values[0]['angle_x_deg'], -12.3)
        self.assertEqual(values[0]['angle_y_deg'], 45.6)


if __name__ == '__main__':
    unittest.main()

"""Phase-stage UART client. No distance calibration or guessed phase unwrapping.

Run with --port COMn; --decode reads a saved binary stream without a serial port.
Configuration is sent only for explicitly supplied --set-* options.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import struct
import sys
import time

MAGIC = b"\xa5\x5a"
CORDIC_GAIN = 1.646760258121


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc


def command(cmd: int, value: int = 0) -> bytes:
    body = struct.pack("<BBBBI", 1, 12, cmd, 0, value)
    return MAGIC + body + struct.pack("<H", crc16(body))


def decode_packet(packet: bytes) -> dict:
    if len(packet) != 64 or packet[:5] != MAGIC + bytes((1, 64, 16)):
        raise ValueError("Unknown packet format")
    if crc16(packet[2:62]) != int.from_bytes(packet[62:], "little"):
        raise ValueError("CRC mismatch")
    flags, adc_ok, channels = packet[5:8]
    sequence, sample_index, high, low = struct.unpack_from("<IIii", packet, 8)
    magnitudes = struct.unpack_from("<4I", packet, 24)
    raw = struct.unpack_from("<8H", packet, 40)
    timeout, threshold, window = struct.unpack_from("<3H", packet, 56)
    if window == 0:
        raise ValueError("Zero-length phase window")
    # Fault bits and startup override numerical phase values. The raw phase is
    # retained only for diagnostics; callers must use high_deg/low_deg.
    common_ok = not (flags & 0xA0)  # warm-up or processing/transport overrun
    high_valid = common_ok and bool(flags & 1) and channels & 5 == 5 and adc_ok & 5 == 5
    low_valid = common_ok and bool(flags & 2) and channels & 10 == 10 and adc_ok & 10 == 10
    result = {
        "sequence": sequence, "sample_index": sample_index,
        "high_deg": high * 360.0 / 2**32 if high_valid else None,
        "low_deg": low * 360.0 / 2**32 if low_valid else None,
        "high_raw_deg": high * 360.0 / 2**32,
        "low_raw_deg": low * 360.0 / 2**32,
        "high_valid": high_valid, "low_valid": low_valid,
        "beam_lost": bool(flags & 4), "flags": flags,
        "adc_ok": adc_ok, "channel_valid": channels,
        "beam_timeout_ms": timeout, "min_amplitude_counts": threshold,
        "window_samples": window,
    }
    for ch, value in enumerate(magnitudes, 1):
        result[f"ch{ch}_peak_counts"] = value * 2 / (window * CORDIC_GAIN)
        result[f"ch{ch}_peak_v"] = result[f"ch{ch}_peak_counts"] * 0.000375
    for ch, value in enumerate(raw, 1):
        result[f"adc{ch}_raw"] = value
        result[f"adc{ch}_v"] = (value - 32768) * 0.000375
    return result


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_packets = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        results = []
        while True:
            at = self.buffer.find(MAGIC)
            if at < 0:
                keep = int(self.buffer.endswith(MAGIC[:1]))
                removed = len(self.buffer) - keep
                self.discarded_bytes += removed
                del self.buffer[:removed]
                break
            if at:
                self.discarded_bytes += at
                del self.buffer[:at]
            if len(self.buffer) < 5:
                break
            if self.buffer[2:5] != bytes((1, 64, 16)):
                self.bad_packets += 1
                del self.buffer[0]
                continue
            if len(self.buffer) < 64:
                break
            try:
                result = decode_packet(bytes(self.buffer[:64]))
            except ValueError:
                self.bad_packets += 1
                del self.buffer[0]
                continue
            del self.buffer[:64]
            results.append(result)
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port", help="USB-TTL serial port, e.g. COM3 (choose your device)")
    source.add_argument("--decode", type=Path, help="saved binary telemetry")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--stale-ms", type=int, default=100, help="host timeout; independent of FPGA beam timer")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--raw", type=Path, help="save received serial bytes")
    parser.add_argument("--set-min-amplitude", type=int)
    parser.add_argument("--set-beam-timeout", type=int)
    parser.add_argument("--set-stream-divider", type=int)
    parser.add_argument("--set-stream", type=int, choices=(0, 1))
    parser.add_argument("--request", action="store_true")
    parser.add_argument("--clear-diagnostics", action="store_true")
    args = parser.parse_args()
    commands = []
    for name, cmd, minimum, maximum in (("set_min_amplitude", 1, 1, 16000),
            ("set_beam_timeout", 2, 1, 60000), ("set_stream_divider", 3, 10, 1000),
            ("set_stream", 4, 0, 1)):
        value = getattr(args, name)
        if value is not None:
            if not minimum <= value <= maximum:
                parser.error(f"--{name.replace('_', '-')} must be {minimum}..{maximum}")
            commands.append(command(cmd, value))
    if args.clear_diagnostics:
        commands.append(command(6))
    if args.request:
        commands.append(command(5))
    if args.seconds <= 0 or args.stale_ms <= 0:
        parser.error("--seconds and --stale-ms must be positive")
    if args.decode and (commands or args.raw):
        parser.error("configuration and --raw require --port")
    decoder = Decoder()
    writer = None
    csv_file = args.csv.open("w", newline="", encoding="utf-8") if args.csv else None
    raw_file = args.raw.open("wb") if args.raw else None
    serial_port = None
    count = 0
    previous_sequence = None
    previous_index = None
    last_print = 0.0
    start = last_good = time.monotonic()
    stale_reported = False
    try:
        if args.port:
            import serial
            serial_port = serial.Serial()
            serial_port.port, serial_port.baudrate = args.port, args.baud
            serial_port.timeout = 0.02
            serial_port.dtr = serial_port.rts = False
            serial_port.open()
            for data in commands:
                serial_port.write(data)
            serial_port.flush()
        file_data = args.decode.read_bytes() if args.decode else None
        while True:
            now = time.monotonic()
            if serial_port:
                if now - start >= args.seconds:
                    break
                data = serial_port.read(min(max(serial_port.in_waiting, 1), 4096))
                if raw_file:
                    raw_file.write(data)
            else:
                data, file_data = file_data, None
                if data is None:
                    break
            for result in decoder.feed(data):
                received = time.monotonic()
                # A CRC-valid repeated/frozen packet is not a fresh measurement.
                seq, idx = result["sequence"], result["sample_index"]
                fresh = previous_sequence is None or (seq != previous_sequence and idx != previous_index)
                result["fresh"] = fresh
                if not fresh:
                    result["high_valid"] = result["low_valid"] = False
                    result["high_deg"] = result["low_deg"] = None
                else:
                    last_good = received
                    stale_reported = False
                result["host_elapsed_s"] = received - start
                result["sequence_step"] = None if previous_sequence is None else (seq - previous_sequence) & 0xFFFFFFFF
                previous_sequence, previous_index = seq, idx
                if csv_file:
                    if writer is None:
                        writer = csv.DictWriter(csv_file, fieldnames=list(result))
                        writer.writeheader()
                    writer.writerow(result)
                count += 1
                if not serial_port or received - last_print >= 0.2:
                    print(json.dumps({k: result[k] for k in ("sequence", "high_deg", "low_deg", "high_valid", "low_valid", "beam_lost", "fresh", "flags")}, ensure_ascii=False), flush=True)
                    last_print = received
            if serial_port and time.monotonic() - last_good > args.stale_ms / 1000 and not stale_reported:
                print(json.dumps({"error": "telemetry_timeout", "high_valid": False, "low_valid": False}), flush=True)
                stale_reported = True
    except KeyboardInterrupt:
        pass
    finally:
        if serial_port:
            serial_port.close()
        if csv_file:
            csv_file.close()
        if raw_file:
            raw_file.close()
    print(f"packets={count} bad_packets={decoder.bad_packets} discarded_bytes={decoder.discarded_bytes}", file=sys.stderr)
    return 0 if count else 2


if __name__ == "__main__":
    raise SystemExit(main())

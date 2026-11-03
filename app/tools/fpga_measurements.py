"""UART v2/v3 decoder and polling client. Requests default to legacy v2.

For atomic DDS configuration use fpga_config.py. No distance is calculated.

Old v1 firmware and recordings use fpga_phase.py. This client never autostarts
a stream: one CRC-protected request is outstanding at a time.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import struct
import time

from fpga_phase import CORDIC_GAIN, MAGIC, crc16

GET_MEASUREMENTS = 2
SET_PARAMETER = 1
WINDOW_SAMPLES = 1000
STATUS = {0: "OK", 1: "NOT_IMPLEMENTED", 2: "UNKNOWN_COMMAND", 3: "BAD_ARGUMENT",
          4: "STAGED", 5: "BUSY", 6: "INCOMPLETE"}


def command(cmd: int = GET_MEASUREMENTS, request_id: int = 0,
            parameter: int = 0, value: int = 0, version: int = 2) -> bytes:
    body = struct.pack("<BBBBHH", version, 12, cmd, parameter, request_id, value)
    return MAGIC + body + struct.pack("<H", crc16(body))


def decode_packet(packet: bytes) -> dict:
    if (len(packet) < 4 or packet[:2] != MAGIC or packet[2] not in (2, 3)
            or len(packet) not in ((12, 96) if packet[2] == 2 else (12, 48, 112))
            or packet[3] != len(packet)):
        raise ValueError("Unknown v2 format")
    if crc16(packet[2:-2]) != int.from_bytes(packet[-2:], "little"):
        raise ValueError("CRC mismatch")
    kind, status = packet[4:6]
    result = {"protocol_version": packet[2], "type": kind, "status": status, "status_name": STATUS.get(status, "UNKNOWN_STATUS"),
              "request_id": int.from_bytes(packet[8:10], "little")}
    if len(packet) == 12:
        if kind not in (0x81, 0x82, 0xff):
            raise ValueError("Unknown ACK type")
        return dict(result, parameter=packet[6], measurement=False)
    if len(packet) == 48:
        if kind != 0x82 or status != 0 or packet[6] != 128:
            raise ValueError("Unknown configuration response")
        channels = [dict(zip(("ftw", "phase_word", "amplitude"), struct.unpack_from("<IHH", packet, 12+8*c))) for c in range(4)]
        return dict(result, measurement=False, configuration=True, channels=channels,
                    generation=int.from_bytes(packet[10:12], "little"), configuring=bool(packet[7] & 1))
    if kind != 0x82 or status != 0:
        raise ValueError("Unknown measurement response")
    flags, digital_flags, adc_ok, channels = packet[6], packet[7], packet[10], packet[11]
    sequence, sample_index = struct.unpack_from("<II", packet, 12)
    phases = struct.unpack_from("<8i", packet, 20)
    magnitudes = struct.unpack_from("<4I", packet, 52)
    samples = struct.unpack_from("<8H", packet, 68)
    digital_sequence, threshold, period_high, period_low = struct.unpack_from("<4H", packet, 84)
    if packet[2] == 3:
        period_high, period_low = struct.unpack_from("<II", packet, 88)
        age, diagnostics = packet[96:98]
        result.update(generation=int.from_bytes(packet[98:100], "little"),
                      delta_high=int.from_bytes(packet[100:104], "little"),
                      delta_low=int.from_bytes(packet[104:108], "little"), configuring=bool(packet[108] & 1))
    else:
        age, diagnostics = packet[92:94]
    max_age = 20 if packet[2] == 3 else 4
    analog_common = not flags & 0xa0  # Warmup or processing overrun.
    ah = analog_common and bool(flags & 1) and channels & 5 == 5 and adc_ok & 5 == 5
    al = analog_common and bool(flags & 2) and channels & 10 == 10 and adc_ok & 10 == 10
    dh = bool(digital_flags & 1) and age < max_age
    dl = bool(digital_flags & 2) and age < max_age
    validities = (ah, al, dh, dl, dh, dh, dl, dl)
    names = ("analog_high", "analog_low", "digital_high", "digital_low",
             "digital_high_rise", "digital_high_fall", "digital_low_rise", "digital_low_fall")
    result.update(measurement=True, sequence=sequence, sample_index=sample_index,
                  digital_sequence=digital_sequence, digital_age_ms=age, flags=flags,
                  digital_flags=digital_flags, diagnostics=diagnostics,
                  adc_ok=adc_ok, channel_valid=channels, beam_lost=bool(flags & 4),
                  min_amplitude_counts=threshold, window_samples=WINDOW_SAMPLES,
                  digital_periods_averaged=16, valid=ah and al and dh and dl and adc_ok == 255)
    for name, phase, valid in zip(names, phases, validities):
        result[name + "_valid"] = valid
        result[name + "_raw_deg"] = phase * 360 / 2**32
        result[name + "_deg"] = result[name + "_raw_deg"] if valid else None
    for name, period in (("high", period_high), ("low", period_low)):
        result["digital_" + name + "_period_ticks"] = period
        result["digital_" + name + "_frequency_hz"] = 125_000_000 / period if period and (dh if name == "high" else dl) else None
    for ch, magnitude in enumerate(magnitudes, 1):
        peak = magnitude * 2 / (WINDOW_SAMPLES * CORDIC_GAIN)
        result[f"ch{ch}_peak_counts"] = peak
        result[f"ch{ch}_peak_v"] = peak * .000375
    for ch, sample in enumerate(samples, 1):
        result[f"adc{ch}_raw"] = sample
        result[f"adc{ch}_v"] = (sample - 32768) * .000375
        if ch >= 5:
            # Voltage at the detector's ADC input, NOT calibrated optical/RF power.
            result[f"detector{ch-4}_raw"] = sample
            result[f"detector{ch-4}_v"] = result[f"adc{ch}_v"] if adc_ok & (1 << (ch-1)) else None
    return result


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_packets = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        results = []
        while self.buffer:
            at = self.buffer.find(MAGIC)
            if at < 0:
                keep = int(self.buffer.endswith(MAGIC[:1]))
                removed = len(self.buffer) - keep
                self.discarded_bytes += removed
                del self.buffer[:removed]
                break
            self.discarded_bytes += at
            del self.buffer[:at]
            if len(self.buffer) < 5:
                break
            length = self.buffer[3]
            if self.buffer[2] not in (2, 3) or length not in ((12, 96) if self.buffer[2] == 2 else (12, 48, 112)):
                self.bad_packets += 1
                del self.buffer[0]
                continue
            if len(self.buffer) < length:
                break
            try:
                result = decode_packet(bytes(self.buffer[:length]))
            except ValueError:
                self.bad_packets += 1
                del self.buffer[0]
                continue
            del self.buffer[:length]
            results.append(result)
        return results


class Freshness:
    """Reject a repeated/frozen epoch even when its frame CRC and request ID match."""
    def __init__(self):
        self.last = None

    def check(self, result: dict) -> dict:
        epoch = (result["sequence"], result["sample_index"], result["digital_sequence"])
        # At 1 kHz digital windows span 16 ms, longer than a 100 Hz UART poll.
        # V3 freshness uses analog counters; the digital live flag/age is separate.
        count = 2 if result.get("protocol_version") == 3 else 3
        fresh = self.last is None or all(a != b for a, b in zip(epoch[:count], self.last[:count]))
        self.last = epoch
        result["fresh"] = fresh
        if not fresh:
            result["valid"] = False
            for key in list(result):
                if key.endswith("_valid") and key.startswith(("analog_", "digital_")):
                    result[key] = False
                if key.endswith("_deg") and not key.endswith("_raw_deg"):
                    result[key] = None
        return result


def transact(port, decoder: Decoder, cmd: int, request_id: int, parameter=0,
             value=0, timeout=.100, raw_file=None, version=2) -> dict:
    port.write(command(cmd, request_id, parameter, value, version))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = port.read(min(max(port.in_waiting, 1), 4096))
        if raw_file:
            raw_file.write(data)
        for result in decoder.feed(data):
            if result["request_id"] == request_id and result["type"] in (cmd | 0x80, 0xff):
                return result
    raise TimeoutError(f"No matching response to request {request_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port")
    source.add_argument("--decode", type=Path)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--poll-hz", type=float, default=100)
    parser.add_argument("--protocol-version", type=int, choices=(2, 3), default=2)
    parser.add_argument("--timeout-ms", type=float, default=100)
    parser.add_argument("--request", action="store_true", help="one GET request")
    parser.add_argument("--set-parameter", type=int, nargs=2, metavar=("ID", "VALUE"),
                        help="send the stub once; expect NOT_IMPLEMENTED")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()
    if args.seconds <= 0 or not 0 < args.poll_hz <= 100 or args.timeout_ms < 30:
        parser.error("seconds > 0, poll-hz 0..100, timeout-ms >= 30 required")
    if args.set_parameter and not (0 <= args.set_parameter[0] <= 255 and 0 <= args.set_parameter[1] <= 65535):
        parser.error("parameter ID must be 0..255, value 0..65535")
    if args.decode and (args.raw or args.request or args.set_parameter):
        parser.error("--raw, --request and --set-parameter require --port")
    decoder, freshness = Decoder(), Freshness()
    count = timeouts = 0
    start = time.monotonic()
    port = csv_file = raw_file = writer = None
    last_print = 0.0

    def emit(result):
        nonlocal writer, count, last_print
        if result.get("measurement"):
            freshness.check(result)
            count += 1
            result["received_elapsed_s"] = time.monotonic() - start
            if csv_file:
                if writer is None:
                    writer = csv.DictWriter(csv_file, fieldnames=list(result))
                    writer.writeheader()
                writer.writerow(result)
            if args.request or args.decode or time.monotonic() - last_print >= 1:
                keys = ("request_id", "valid", "beam_lost", "analog_high_deg", "analog_low_deg",
                        "digital_high_deg", "digital_low_deg", "detector1_v", "detector2_v",
                        "detector3_v", "detector4_v")
                print(json.dumps({k: result[k] for k in keys}), flush=True)
                last_print = time.monotonic()
        else:
            print(json.dumps(result), flush=True)

    try:
        if args.csv:
            csv_file = args.csv.open("w", newline="", encoding="utf-8")
        if args.decode:
            for result in decoder.feed(args.decode.read_bytes()):
                emit(result)
        else:
            import serial
            port = serial.Serial()
            port.port, port.baudrate, port.timeout = args.port, 115200, .002
            port.write_timeout = .1
            port.dtr = port.rts = False
            port.open()
            if args.raw:
                raw_file = args.raw.open("wb")
            request_id = 0
            while time.monotonic() - start < args.seconds:
                cycle_start = time.monotonic()
                cmd = SET_PARAMETER if args.set_parameter else GET_MEASUREMENTS
                parameter, value = args.set_parameter or (0, 0)
                try:
                    result = transact(port, decoder, cmd, request_id, parameter, value,
                                      args.timeout_ms / 1000, raw_file, version=args.protocol_version)
                    emit(result)
                except TimeoutError as error:
                    timeouts += 1
                    # No interpolation: a timeout explicitly removes validity.
                    print(json.dumps({"request_id": request_id, "valid": False,
                                      "error": str(error)}), flush=True)
                request_id = (request_id + 1) & 65535
                if args.request or args.set_parameter:
                    break
                time.sleep(max(0, cycle_start + 1/args.poll_hz - time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        for handle in (port, csv_file, raw_file):
            if handle:
                handle.close()
    print(json.dumps({"measurements": count, "timeouts": timeouts, "bad_packets": decoder.bad_packets}), flush=True)
    return 1 if timeouts else 0


if __name__ == "__main__":
    raise SystemExit(main())

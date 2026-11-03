"""Explicit UART v3 client. Never opens a port unless invoked with --port.

DDS configuration JSON: {"channels": [{"ftw": ..., "phase_word": ...,
"amplitude": ...}, ... four channels in physical CH0..CH3 order]}.
Use exact FTWs to preserve the intended frequency differences.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path
from fpga_measurements import Decoder, transact

DEFAULT_CHANNELS = [dict(ftw=f, phase_word=0, amplitude=a) for f, a in
                    [(12845056, 200), (635888254, 1000), (12879416, 1000), (635830272, 450)]]


def validate(channels):
    if not isinstance(channels, list) or len(channels) != 4:
        raise ValueError("Exactly four channels in CH0..CH3 order are required")
    for ch in channels:
        for key, lo, hi in (("ftw", 1, 0x7fffffff), ("phase_word", 0, 16383), ("amplitude", 0, 1023)):
            if type(ch.get(key)) is not int or not lo <= ch[key] <= hi:
                raise ValueError(f"{key} must be an integer in {lo}..{hi}")
    dh = channels[1]["ftw"]-channels[3]["ftw"]
    dl = channels[2]["ftw"]-channels[0]["ftw"]
    if not (8590 <= dh <= 171799 and 8590 <= dl <= 171799):
        raise ValueError("Positive IF FTW differences must be 8590..171799 (about 1..20 kHz)")
    return struct.pack("<"+"IHH"*4, *(ch[key] for ch in channels for key in ("ftw", "phase_word", "amplitude")))


class ConfigurationClient:
    def __init__(self, port, timeout=.25, raw_file=None):
        self.port, self.timeout = port, timeout
        self.raw_file = raw_file
        self.decoder, self.request_id = Decoder(), 0

    def request(self, command=2, parameter=0, value=0, expected=0):
        self.request_id = (self.request_id+1) & 65535
        result = transact(self.port, self.decoder, command, self.request_id, parameter, value,
                          timeout=self.timeout, version=3, raw_file=self.raw_file)
        if result.get('protocol_version') != 3:
            raise RuntimeError('Expected UART protocol v3')
        if result["status"] != expected:
            raise RuntimeError(f"FPGA returned {result['status_name']}")
        return result

    def read(self):
        result = self.request(parameter=1)
        if not result.get('configuration'):
            raise RuntimeError('Expected an active configuration bank')
        return result

    def apply(self, channels):
        data = validate(channels)  # Validate before BEGIN or any device side effect.
        self.request(1, 0xf0, 0xb001, 4)
        for word, value in enumerate(struct.unpack("<16H", data)):
            self.request(1, 0x10+word, value, 4)
        # Do not automatically retry COMMIT after a timeout: read back state first.
        self.request(1, 0xf1, 0xa55a)
        result = self.read()
        if validate(result["channels"]) != data:
            raise RuntimeError("Active FPGA settings differ from the requested bank")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read-config", action="store_true")
    mode.add_argument("--request", action="store_true")
    mode.add_argument("--set-config", type=Path)
    mode.add_argument("--defaults-json", action="store_true")
    args = parser.parse_args()
    if args.defaults_json:
        print(json.dumps({"channels": DEFAULT_CHANNELS}, indent=2));return
    if not args.port:
        parser.error("--port is required for device access")
    channels = json.loads(args.set_config.read_text(encoding="utf-8"))["channels"] if args.set_config else None
    if channels is not None:
        validate(channels)
    import serial
    with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.25) as port:
        client = ConfigurationClient(port)
        result = client.apply(channels) if channels is not None else (client.read() if args.read_config else client.request())
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

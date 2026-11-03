"""CONDTROL Vector 60 BLE CLI. Protocol recovered from supplied APK 1.026."""
import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SERVICE = '0000ffb0-0000-1000-8000-00805f9b34fb'
CHAR = '0000ffb2-0000-1000-8000-00805f9b34fb'


def decode_frame(data):
    if len(data) not in (9, 17) or data[:3] != b'ATD' or data[-1:] != b'#':
        raise ValueError('Expected binary ATD frame, 9 or 17 bytes ending in #')
    result = {'distance_m': int.from_bytes(data[3:7], 'big', signed=True) / 10000,
              'angle_x_deg': None, 'angle_y_deg': None, 'raw_hex': data.hex(' ')}
    if len(data) == 17:
        result.update(angle_x_deg=int.from_bytes(data[7:11], 'big', signed=True) / 10,
                      angle_y_deg=int.from_bytes(data[11:15], 'big', signed=True) / 10)
    return result


class FrameParser:
    """Fixed configured length avoids treating binary # inside payload as delimiter."""
    def __init__(self, size=9):
        self.size = size
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while True:
            start = self.buffer.find(b'ATD')
            if start < 0:
                self.buffer[:] = self.buffer[-2:]
                break
            del self.buffer[:start]
            if len(self.buffer) < self.size:
                break
            if self.buffer[self.size - 1] != 35:
                del self.buffer[0]
                continue
            frames.append(decode_frame(bytes(self.buffer[:self.size])))
            del self.buffer[:self.size]
        return frames


def utc():
    return datetime.now(timezone.utc).isoformat()


class Recorder:
    def __init__(self, folder):
        folder.mkdir(parents=True, exist_ok=False)
        self.folder = folder
        self.events = (folder / 'events.jsonl').open('w', encoding='utf-8')
        self.csvfile = (folder / 'measurements.csv').open('w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.csvfile, fieldnames=[
            'utc', 'monotonic_s', 'request_id', 'distance_m', 'angle_x_deg', 'angle_y_deg', 'raw_hex'])
        self.writer.writeheader()

    def event(self, kind, **values):
        record = dict(utc=utc(), monotonic_s=time.monotonic(), kind=kind, **values)
        self.events.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.events.flush()
        print(json.dumps(record, ensure_ascii=True), flush=True)
        return record

    def measurement(self, request_id, value):
        record = self.event('measurement', request_id=request_id, **value)
        record.pop('kind')
        self.writer.writerow(record)
        self.csvfile.flush()

    def close(self):
        self.events.close()
        self.csvfile.close()


def load_bleak():
    import bleak
    return bleak


async def operate(args, log):
    bleak = load_bleak()
    found = await bleak.BleakScanner.discover(timeout=args.scan_timeout, return_adv=True)
    candidates = []
    for device, adv in found.values():
        name = adv.local_name or device.name or ''
        address_type = None
        if sys.platform == 'win32' and len(adv.platform_data) > 1:
            packet = adv.platform_data[1].adv or adv.platform_data[1].scan
            if packet is not None:
                address_type = str(getattr(packet, 'bluetooth_address_type', None))
        log.event('discovered', name=name, address=device.address, rssi=adv.rssi,
                  services=adv.service_uuids, address_type=address_type)
        if args.address:
            match = device.address.lower() == args.address.lower()
        else:
            match = 'vector60' in name.lower().replace(' ', '').replace('_', '')
        if match:
            candidates.append(device)
    if args.action == 'scan':
        return
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one Vector 60, found {len(candidates)}; use --address or enable device Bluetooth')
    target = candidates[0]
    log.event('connecting', address=target.address, name=target.name)
    extra = {}
    if sys.platform == 'win32' and args.retry_services:
        from bleak.backends.winrt.client import BleakClientWinRT

        class RetryServices(BleakClientWinRT):
            # Bleak 3.0.2 internal workaround, opt-in and version-pinned.
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._retry_on_services_changed = True
        extra['backend'] = RetryServices
    async with bleak.BleakClient(target, timeout=args.connect_timeout,
                                pair=args.pair,
                                services=[SERVICE] if args.service_filter else None,
                                winrt={**({'use_cached_services': args.cached_services} if not args.auto_cache else {}),
                                       **({'address_type': args.address_type} if args.address_type else {})}, **extra) as client:
        log.event('connected', address=target.address)
        for service in client.services:
            log.event('service', uuid=service.uuid, characteristics=[
                {'uuid': c.uuid, 'handle': c.handle, 'properties': c.properties}
                for c in service.characteristics])
        char = client.services.get_characteristic(CHAR)
        if char is None or char.service_uuid != SERVICE:
            raise RuntimeError('Expected FFB0/FFB2 not found')
        if args.action == 'inspect':
            return
        if not any(p in char.properties for p in ('notify', 'indicate')):
            raise RuntimeError('FFB2 does not support notification or indication')
        parser = FrameParser(args.frame_size)
        queue = asyncio.Queue()
        request_id = None

        def received(sender, data):
            log.event('rx', hex=bytes(data).hex(' '))
            for value in parser.feed(data):
                log.measurement(request_id, value)
                queue.put_nowait(value)

        await client.start_notify(char, received)
        try:
            if args.action == 'listen':
                deadline = time.monotonic() + args.duration
                while time.monotonic() < deadline:
                    if not client.is_connected:
                        raise ConnectionError('Vector disconnected while listening')
                    await asyncio.sleep(min(.2, max(0, deadline - time.monotonic())))
            else:
                if not any(p in char.properties for p in ('write', 'write-without-response')):
                    raise RuntimeError('FFB2 is not writable')
                for index in range(args.count):
                    request_id = index + 1
                    # Drop pre-command input, never return a queued old measurement.
                    while not queue.empty():
                        queue.get_nowait()
                    parser.buffer.clear()
                    command = b'ATK001#' if args.action == 'measure' else b'ATD001#'
                    log.event('tx', request_id=request_id, hex=command.hex(' '), command=command.decode())
                    # Captured SmartMeasure exchange uses Write Without Response.
                    await client.write_gatt_char(char, command, response='write-without-response' not in char.properties)
                    try:
                        await asyncio.wait_for(queue.get(), timeout=args.result_timeout)
                    except TimeoutError:
                        raise TimeoutError('No ATD measurement after command; see raw events (ATK acknowledgement is not a distance)') from None
                    request_id = None
                    if index + 1 < args.count:
                        await asyncio.sleep(args.interval)
        finally:
            if client.is_connected:
                await client.stop_notify(char)
    log.event('disconnected')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['scan', 'inspect', 'listen', 'measure', 'request'])
    p.add_argument('--address', help='Explicit BLE MAC; default discover Vector 60 by name')
    p.add_argument('--scan-timeout', type=float, default=12)
    p.add_argument('--connect-timeout', type=float, default=25)
    p.add_argument('--result-timeout', type=float, default=12)
    p.add_argument('--duration', type=float, default=20)
    p.add_argument('--frame-size', type=int, choices=[9, 17], default=9)
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--interval', type=float, default=1)
    p.add_argument('--out', type=Path)
    p.add_argument('--cached-services', action='store_true')
    p.add_argument('--retry-services', action='store_true', help='WinRT Services Changed workaround for Bleak 3.0.2')
    p.add_argument('--pair', action='store_true', help='Request OS pairing (normally unnecessary for this device)')
    p.add_argument('--service-filter', action='store_true', help='Discover only FFB0 service')
    p.add_argument('--auto-cache', action='store_true', help='Let Windows choose service caching')
    p.add_argument('--address-type', choices=['public', 'random'], help='Explicit WinRT BLE address type')
    args = p.parse_args()
    if args.count < 1 or min(args.scan_timeout, args.connect_timeout, args.result_timeout, args.duration) <= 0 or args.interval < 0:
        p.error('Timeouts/duration/count must be positive; interval must be nonnegative')
    folder = args.out or ROOT / 'captures/vector60' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    log = Recorder(folder)
    logging.basicConfig(filename=folder / 'bleak.log', level=logging.DEBUG,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')
    status = 0
    try:
        log.event('start', arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, python=sys.version)
        asyncio.run(operate(args, log))
        log.event('completed')
    except KeyboardInterrupt:
        log.event('interrupted')
        status = 130
    except Exception as exc:
        log.event('error', error=repr(exc))
        status = 1
    finally:
        log.close()
        print('Saved:', folder, flush=True)
    return status


if __name__ == '__main__':
    sys.exit(main())

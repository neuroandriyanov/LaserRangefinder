"""Vector 60 via dedicated WinUSB Bluetooth adapter; never uses UsbDk."""
import argparse
import asyncio
from datetime import datetime, timezone
import logging
import re
import sys
from vector60 import ROOT, Recorder
from vector60_usb import DirectVector, TARGET, USB_TRANSPORT


def check_driver(transport):
    if sys.platform != 'win32':
        raise RuntimeError('The Vector60 WinUSB backend requires Windows.')
    match = re.fullmatch(r'usb:([0-9a-fA-F]{4}):([0-9a-fA-F]{4})', transport)
    if not match:
        raise ValueError('Use usb:VID:PID with four hexadecimal digits per identifier.')
    device_id = f'VID_{match[1].upper()}&PID_{match[2].upper()}'
    import ctypes
    import winreg
    # Do not coexist with the experimental kernel filter, even if stopped.
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SYSTEM\CurrentControlSet\Services\UsbDk'):
            raise RuntimeError('UsbDk is still registered; remove it before using this backend')
    except FileNotFoundError:
        pass
    services = []
    cm = ctypes.WinDLL('cfgmgr32')
    cm.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_wchar_p, ctypes.c_ulong]
    cm.CM_Locate_DevNodeW.restype = ctypes.c_ulong
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            'SYSTEM\\CurrentControlSet\\Enum\\USB\\' + device_id) as parent:
        for i in range(winreg.QueryInfoKey(parent)[0]):
            name = winreg.EnumKey(parent, i)
            node = ctypes.c_ulong()
            if cm.CM_Locate_DevNodeW(ctypes.byref(node), 'USB\\' + device_id + '\\' + name, 0) != 0:
                continue  # old instances from other USB ports are not attached
            with winreg.OpenKey(parent, name) as instance:
                try:
                    services.append(winreg.QueryValueEx(instance, 'Service')[0])
                except FileNotFoundError:
                    continue
    if len(services) != 1 or services[0].lower() != 'winusb':
        raise RuntimeError(f'{device_id} requires one attached WinUSB adapter; current services: {services}')


class WinUsbVector(DirectVector):
    usb_transport = USB_TRANSPORT

    async def open(self):
        check_driver(self.usb_transport)
        import usb1
        from bumble.transport import usb, open_transport
        from bumble.device import Device
        from bumble.hci import Address
        # usb1 bundles libusb 1.0.29. Keep its default Windows/WinUSB backend.
        usb1.loadLibrary()
        usb.load_libusb = lambda: None
        self.log.event('opening_adapter', transport=self.usb_transport, backend='WinUSB')
        self.transport = await open_transport(self.usb_transport)
        self.device = Device.with_hci('Vector60-PC', Address.ANY,
                                     self.transport.source, self.transport.sink)
        await asyncio.wait_for(self.device.power_on(), 25)
        self.log.event('adapter_ready', public_address=str(self.device.public_address))


def capture_folder(backend='winusb'):
    return ROOT / 'captures/vector60' / (datetime.now(timezone.utc).strftime(
        '%Y%m%dT%H%M%S_%fZ') + '-' + backend)


async def operate(args, log):
    client = WinUsbVector(log)
    client.usb_transport = args.usb_transport
    try:
        await client.open()
        if args.action == 'controller':
            return
        if args.action == 'scan':
            await client.scan(args.scan_timeout)
            return
        await client.connect(args.address)
        if args.action == 'measure':
            for i in range(args.count):
                await client.measure(args.timeout)
                if i + 1 < args.count:
                    await asyncio.sleep(args.interval)
        elif args.action == 'listen':
            await asyncio.sleep(args.duration)
    finally:
        await client.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['controller', 'scan', 'inspect', 'measure', 'listen'])
    p.add_argument('--address', default=TARGET)
    p.add_argument('--usb-transport', default=USB_TRANSPORT, help='Dedicated adapter: usb:VID:PID')
    p.add_argument('--scan-timeout', type=float, default=10)
    p.add_argument('--timeout', type=float, default=12)
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--interval', type=float, default=1)
    p.add_argument('--duration', type=float, default=20)
    args = p.parse_args()
    if args.action not in ('controller','scan') and not args.address:
        p.error('--address is required; use scan to find your Vector60')
    if args.count < 1 or min(args.scan_timeout, args.timeout, args.duration) <= 0 or args.interval < 0:
        p.error('Count/timeouts must be positive; interval nonnegative')
    log = Recorder(capture_folder())
    logging.basicConfig(filename=log.folder / 'bluetooth.log', level=logging.DEBUG)
    try:
        log.event('start', backend='WinUSB', arguments=vars(args))
        asyncio.run(operate(args, log))
        return 0
    except KeyboardInterrupt:
        log.event('interrupted')
        return 130
    except Exception as exc:
        log.event('error', error=repr(exc))
        return 1
    finally:
        log.close()
        print('Saved:', log.folder)


if __name__ == '__main__':
    sys.exit(main())

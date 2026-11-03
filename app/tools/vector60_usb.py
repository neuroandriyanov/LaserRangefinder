"""Transport-independent Vector60 commands and response parser integration."""
import asyncio
from vector60 import FrameParser

TARGET = ""
USB_TRANSPORT = "usb:0B05:1D70"


class DirectVector:
    def __init__(self, log):
        self.log = log
        self.transport = None
        self.device = None
        self.connection = None
        self.characteristic = None
        self.samples = asyncio.Queue()
        self.parser = FrameParser(9)
        self.request_id = None
        self.request_counter = 0
        self.measure_lock = asyncio.Lock()

    async def open(self):
        raise NotImplementedError("Use WinUsbVector for the supported Windows transport")

    async def scan(self, seconds=8):
        def on_advertisement(adv):
            self.log.event('advertisement', address=str(adv.address), rssi=adv.rssi,
                           data_hex=bytes(adv.data).hex(' '))
        self.device.on('advertisement', on_advertisement)
        try:
            await self.device.start_scanning(legacy=True)
            await asyncio.sleep(seconds)
        finally:
            await self.device.stop_scanning()
            self.device.remove_listener('advertisement', on_advertisement)

    async def connect(self, address=TARGET):
        if not address:
            raise ValueError("Specify your Vector60 Bluetooth address")
        from bumble.device import Peer
        from bumble.hci import Address
        from bumble.core import UUID
        self.log.event('connecting', address=address)
        self.connection = await self.device.connect(
            Address(address, Address.PUBLIC_DEVICE_ADDRESS), timeout=20)
        self.connection.on('disconnection', self.on_disconnect)
        peer = Peer(self.connection)
        # Do not discover/read Generic Access/PPCP. Only the measured FFB0 service.
        async with asyncio.timeout(15):
            services = await peer.discover_service(UUID.from_16_bits(0xffb0))
            if len(services) != 1:
                raise RuntimeError('FFB0 service not found or ambiguous')
            chars = await peer.discover_characteristics(service=services[0])
            for char in chars:
                self.log.event('characteristic', uuid=str(char.uuid), handle=char.handle,
                               properties=int(char.properties))
                if char.uuid == UUID.from_16_bits(0xffb2):
                    self.characteristic = char
            if self.characteristic is None:
                raise RuntimeError('FFB2 characteristic not found')
            await self.characteristic.subscribe(self.on_data)
        self.log.event('connected', address=address)

    def on_disconnect(self, reason):
        self.characteristic = None
        self.connection = None
        self.log.event('device_disconnected', reason=int(reason))

    def on_data(self, data):
        raw = bytes(data)
        self.log.event('rx', hex=raw.hex(' '))
        for sample in self.parser.feed(raw):
            self.log.measurement(self.request_id, sample)
            self.samples.put_nowait(sample)

    async def measure(self, timeout=12, repeat_interval=1.0):
        async with self.measure_lock:
            if self.characteristic is None:
                raise ConnectionError('Vector 60 is not connected')
            self.request_counter += 1
            self.request_id = self.request_counter
            while not self.samples.empty():
                self.samples.get_nowait()
            self.parser.buffer.clear()
            deadline = asyncio.get_running_loop().time() + timeout
            try:
                while True:
                    if self.characteristic is None:
                        raise ConnectionError('Vector 60 disconnected while measuring')
                    command = b'ATK001#'
                    self.log.event('tx', request_id=self.request_id, hex=command.hex(' '))
                    await self.characteristic.write_value(command, with_response=False)
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise TimeoutError('No ATD distance received')
                    try:
                        return await asyncio.wait_for(self.samples.get(), min(repeat_interval, remaining))
                    except TimeoutError:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise TimeoutError('No ATD distance received') from None
            finally:
                self.request_id = None

    async def close(self):
        if self.connection:
            try:
                await asyncio.wait_for(self.connection.disconnect(), 3)
            except Exception as exc:
                self.log.event('disconnect_error', error=repr(exc))
        if self.transport:
            await self.transport.close()
            self.transport = None
            self.log.event('adapter_released')


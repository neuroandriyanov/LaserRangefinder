"""Behavior tests: persistence, invalid data, pairing, cancellation and wire polling."""
import asyncio
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from .model import DEFAULTS, History, SettingsStore, dds_channels, validate_dds, validate_settings
from .workers import DeviceWorker, InterruptiblePort, vector_cycle
from test_fpga_measurements import telemetry
from fpga_measurements import Decoder, GET_MEASUREMENTS, transact


class SettingsTests(unittest.TestCase):
    def test_first_launch_defaults_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            store = SettingsStore(Path(d) / "config/settings.json")
            s, warning = store.load()
            self.assertEqual((s["port"], s["baud"], s["fpga_interval_ms"], s["vector_timeout_s"]), (DEFAULTS['port'], 115200, 10, 3))
            self.assertFalse(warning)
            s.update(port="COM12", fpga_interval_ms=25, vector_timeout_s=5, vector_enabled=True, x_axis="distance")
            s["dds"][0]["frequency_mhz"] = 2.25
            store.save(s)
            self.assertEqual(store.load()[0], s)
            self.assertEqual(DEFAULTS['vector_address'], '')

    def test_corrupt_settings_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text('{broken', encoding="utf-8")
            s, warning = SettingsStore(p).load()
            self.assertEqual(s, DEFAULTS)
            self.assertTrue(warning)
            self.assertEqual(p.read_text(), '{broken')
            self.assertEqual(len(list(Path(d).glob("settings-invalid-*.json"))), 1)

    def test_invalid_settings_never_replace_good_file(self):
        with tempfile.TemporaryDirectory() as d:
            store = SettingsStore(Path(d) / "settings.json")
            store.save(DEFAULTS)
            before = store.path.read_bytes()
            for key, value in (("fpga_interval_ms", 0), ("vector_timeout_s", "nan"), ("baud", -1), ("history_s", 1), ("parity", "Z")):
                bad = deepcopy(DEFAULTS);bad[key] = value
                with self.assertRaises(ValueError):store.save(bad)
                self.assertEqual(store.path.read_bytes(), before)

    def test_dds_boundaries_and_current_registers(self):
        result = dds_channels(DEFAULTS["dds"])
        self.assertEqual([r["ftw"] for r in result], [12845056, 635888254, 12879416, 635830272])
        for key, value in (("frequency_mhz", 250), ("frequency_mhz", -1), ("phase_deg", 360), ("phase_deg", "inf"), ("amplitude", 1024), ("amplitude", .5)):
            bad = deepcopy(DEFAULTS["dds"]);bad[2][key] = value
            with self.assertRaises(ValueError):validate_dds(bad)
        rows = deepcopy(DEFAULTS["dds"]);rows[0].update(frequency_mhz="1,5", phase_deg="90", amplitude="0")
        self.assertEqual(dds_channels(rows, check_if=False)[0]["phase_word"], 4096)

    def test_dds_phase_offsets_survive_restart_and_reach_register_bank(self):
        settings = deepcopy(DEFAULTS)
        for row, phase in zip(settings["dds"], (0, 90, 180, 270)):
            row["phase_deg"] = phase
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder) / "settings.json")
            store.save(settings)
            restored, warning = SettingsStore(store.path).load()
            self.assertFalse(warning)
            result = dds_channels(restored["dds"])
        self.assertEqual([row["phase_word"] for row in result], [0, 4096, 8192, 12288])


class HistoryTests(unittest.TestCase):
    def test_low_amplitude_is_preserved_when_phase_is_invalid(self):
        h=History()
        h.add_fpga(1,dict(valid=False,fresh=True,adc_ok=255,analog_high_deg=None,ch3_peak_v=.001))
        self.assertEqual(h.series('ch3_peak_v','time',60)[1],[.001])
        self.assertTrue(math.isnan(h.series('analog_high_deg','time',60)[1][0]))

    def test_pair_only_fresh_previous_sample(self):
        h = History()
        h.add_fpga(1, {"valid": True, "analog_high_deg": 20})
        h.add_fpga(1.06, {"valid": True, "analog_high_deg": 30})
        h.add_vector(1.05, 1200)
        self.assertEqual(h.series("analog_high_deg", "distance", 60), ([1200], [20]))
        h.add_vector(2, 1250)
        x, y = h.series("analog_high_deg", "distance", 60)
        self.assertTrue(math.isnan(y[-1]))
        self.assertEqual(x[-1], 1250)

    def test_invalid_and_timeout_break_lines(self):
        h = History()
        h.add_fpga(1, {"valid": True, "analog_high_deg": 15})
        h.add_fpga(1.02, {"valid": False, "analog_high_deg": 15})
        h.add_vector(1.03, 1000)
        self.assertTrue(math.isnan(h.series("analog_high_deg", "distance", 60)[1][0]))
        self.assertTrue(math.isnan(h.series("analog_high_deg", "time", 60)[1][-1]))
        h.add_vector(2, None)
        self.assertTrue(math.isnan(h.series("vector_mm", "distance", 60)[0][-1]))

    def test_history_is_bounded_and_time_window_is_respected(self):
        h = History(capacity=3)
        for t in range(5):h.add_fpga(t, {"valid": True, "analog_high_deg": t})
        self.assertEqual(len(h.fpga), 3)
        self.assertEqual(h.series("analog_high_deg", "time", 1)[0], [3, 4])


class SerialTests(unittest.TestCase):
    def test_cancellation_interrupts_long_deadline(self):
        stop = threading.Event()
        class Port:
            in_waiting = 0
            def write(self, data):stop.set()
            def read(self, size):return b""
        with self.assertRaises(InterruptedError):
            transact(InterruptiblePort(Port(), stop), Decoder(), GET_MEASUREMENTS, 0, timeout=10)

    def test_worker_uses_saved_serial_settings_and_closes(self):
        events = []
        from .test_v3 import FakeV3Port
        port = FakeV3Port()
        with tempfile.TemporaryDirectory() as d, patch("serial.Serial", return_value=port):
            s = deepcopy(DEFAULTS);s["port"] = "COM17"
            worker = DeviceWorker("fpga", s, events.append, log_base=d)
            worker.start()
            deadline = time.monotonic()+2
            while len([r for r in events if r['kind']=='sample']) < 3 and time.monotonic() < deadline:time.sleep(.01)
            worker.stop();worker.thread.join(2)
            self.assertFalse(worker.alive)
            self.assertTrue(port.closed)
            self.assertEqual(port.asserted, ("COM17",115200,8,"N",1,False,False))
            rows=[e['row'] for e in events if e['kind']=='sample']
            self.assertGreaterEqual(len(rows),3)
            self.assertTrue(all(r['valid'] for r in rows))
            self.assertEqual(events[-1]['kind'],'stopped')
            self.assertTrue(list(Path(d).rglob('uart.bin')))
            csv_path=next(Path(d).rglob('*.csv'))
            header=csv_path.read_text(encoding='utf-8').splitlines()[0].split(',')
            self.assertNotIn('phase_distance_mm',header)


class VectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_measurement_timeouts_restart_poll_without_reconnecting(self):
        from types import SimpleNamespace
        class Client:
            instances = []
            def __init__(self, log):
                self.device = SimpleNamespace(connect=self.connect)
                self.calls = self.closes = self.connects = 0
                self.instances.append(self)
            async def open(self):pass
            async def connect(self, *a, **kw):self.connects += 1
            async def measure(self, **kw):
                self.calls += 1
                if self.calls <= 2:
                    raise TimeoutError("No ATD")
                return {"distance_m": 1.234}
            async def close(self):self.closes += 1
        events = []
        def emit(event):
            events.append(event)
            if event["kind"] == "sample":
                worker.stop_event.set()
        settings = deepcopy(DEFAULTS)
        settings["vector_interval_s"] = .01
        settings['vector_address'] = 'AA:BB:CC:DD:EE:FF'
        with tempfile.TemporaryDirectory() as folder, patch("vector60_winusb.WinUsbVector", Client):
            worker = DeviceWorker("vector", settings, emit, log_base=folder)
            await asyncio.wait_for(worker.run_vector(), 2)
        self.assertEqual(len(Client.instances), 1)
        self.assertEqual((Client.instances[0].connects, Client.instances[0].closes), (1, 1))
        self.assertEqual([e["kind"] for e in events if e["kind"] in ("sample", "timeout")], ["timeout", "timeout", "sample"])
        self.assertEqual([e["distance_mm"] for e in events if e["kind"] == "sample"], [1234])

    async def test_stop_during_vector_reply_releases_client_once(self):
        from types import SimpleNamespace
        class Client:
            instances=[]
            def __init__(self,log):
                self.device=SimpleNamespace(connect=self.connect)
                self.measuring=False;self.closes=0;self.instances.append(self)
            async def open(self):pass
            async def connect(self,*a,**kw):pass
            async def measure(self,**kw):
                self.measuring=True
                await asyncio.sleep(10)
            async def close(self):self.closes+=1
        with tempfile.TemporaryDirectory() as d, patch('vector60_winusb.WinUsbVector',Client):
            worker=DeviceWorker('vector',dict(DEFAULTS,vector_address='AA:BB:CC:DD:EE:FF'),lambda e:None,log_base=d)
            task=asyncio.create_task(worker.run_vector())
            for _ in range(50):
                if Client.instances and Client.instances[0].measuring:break
                await asyncio.sleep(.005)
            self.assertTrue(Client.instances[0].measuring)
            worker.stop()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(Client.instances[0].closes,1)

    async def test_single_command_until_timeout(self):
        from vector60_usb import DirectVector
        class Log:
            def event(self,*args,**kwargs):pass
        class Char:
            calls=0
            async def write_value(self,data,with_response):self.calls+=1
        client=DirectVector(Log());client.characteristic=Char()
        with self.assertRaises(TimeoutError):
            await client.measure(timeout=.04,repeat_interval=.04)
        self.assertEqual(client.characteristic.calls,1)
        self.assertIsNone(client.request_id)

    async def test_original_atk_retry_receives_answer(self):
        from vector60_usb import DirectVector
        class Log:
            def event(self, *args, **kwargs):pass
        client = DirectVector(Log())
        class Characteristic:
            calls = 0
            async def write_value(self, data, with_response):
                self.calls += 1
                if self.calls == 2:
                    client.samples.put_nowait({"distance_m": 2.345})
        client.characteristic = Characteristic()
        events = []
        await vector_cycle(client, {"vector_interval_s": .01, "vector_timeout_s": 2},
                           lambda kind, **values: events.append(values))
        self.assertEqual(client.characteristic.calls, 2)
        self.assertEqual(events, [{"distance_mm": 2345}])
        self.assertIsNone(client.request_id)

    async def test_next_cycle_waits_for_answer(self):
        class Client:
            active=maximum=0
            def __init__(self):self.times=[]
            async def measure(self,timeout,repeat_interval):
                self.active+=1;self.maximum=max(self.maximum,self.active);self.times.append(time.monotonic())
                self.asserted=(timeout,repeat_interval)
                await asyncio.sleep(.04)
                self.active-=1
                return {"distance_m":1.234}
        client=Client();events=[]
        for _ in range(2):await vector_cycle(client,{"vector_interval_s":.01,"vector_timeout_s":.2},lambda kind,**kw:events.append(kw))
        self.assertEqual(client.maximum,1)
        self.assertGreaterEqual(client.times[1]-client.times[0],.049)
        self.assertEqual(client.asserted,(.2,1.0))
        self.assertEqual(events[0]["distance_mm"],1234)

    async def test_timeout_has_no_fabricated_measurement(self):
        class Client:
            async def measure(self,**kw):await asyncio.sleep(1)
        events=[]
        with self.assertRaises(TimeoutError):
            await vector_cycle(Client(),{"vector_interval_s":.01,"vector_timeout_s":.03},lambda *a,**k:events.append(k))
        self.assertEqual(events,[])


if __name__ == "__main__":
    unittest.main()

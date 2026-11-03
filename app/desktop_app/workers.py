"""Single-owner device workers. Tk widgets are never touched from these threads."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
from functools import partial
import json
import math
from copy import deepcopy
import queue
from pathlib import Path
import sys
import threading
import time

from .model import ROOT, dds_channels

sys.path.insert(0, str(ROOT / "tools"))
from fpga_measurements import Decoder, Freshness, GET_MEASUREMENTS, transact
from fpga_config import ConfigurationClient, validate as validate_channels


class InterruptiblePort:
    def __init__(self, port, stop, log=None):
        self.port, self.stop = port, stop
        self.log = log

    def check(self):
        if self.stop.is_set():
            raise InterruptedError("Опрос остановлен.")

    @property
    def in_waiting(self):
        self.check()
        return self.port.in_waiting

    def write(self, data):
        self.check()
        if self.log:
            self.log.event('tx', monotonic=time.monotonic(), hex=data.hex())
        return self.port.write(data)

    def read(self, size):
        self.check()
        return self.port.read(size)


class Journal:
    def __init__(self, kind, settings, base=None):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        self.folder = Path(base or ROOT / "captures/desktop-app") / f"{stamp}-{kind}"
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder / "settings.json").write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        self.file = (self.folder / "events.jsonl").open("w", encoding="utf-8")

    def event(self, kind, **data):
        self.file.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), kind=kind, **data), ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self):
        self.file.close()


class DeviceWorker:
    def __init__(self, source, settings, emit, demo=False, log_base=None, polling=True):
        self.source, self.settings, self.emit = source, deepcopy(settings), emit
        self.demo, self.log_base = demo, log_base
        self.polling = polling
        self.commands = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"rangefinder-{source}", daemon=True)
        self.loop = self.task = None

    def start(self):
        self.thread.start()

    def submit(self, action, channels=None):
        if action not in ('read', 'apply') or self.source != 'fpga':
            raise ValueError('Неизвестная операция DDS.')
        if action == 'apply':
            validate_channels(channels)
        if self.stop_event.is_set():
            raise RuntimeError('Дождитесь остановки COM-порта.')
        self.commands.put((action, deepcopy(channels)))

    def stop(self):
        already = self.stop_event.is_set()
        self.stop_event.set()
        if not already and self.loop and self.task:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass

    @property
    def alive(self):
        return self.thread.is_alive()

    def publish(self, kind, **values):
        self.emit(dict(source=self.source, kind=kind, monotonic=time.monotonic(), **values))

    def run(self):
        try:
            if self.demo:
                self.run_demo()
            elif self.source == "fpga":
                self.run_fpga()
            else:
                asyncio.run(self.run_vector())
        except (InterruptedError, asyncio.CancelledError):
            pass
        except Exception as error:
            self.publish("error", message=f"Не удалось продолжить: {error}")
        finally:
            self.publish("stopped")

    def run_fpga(self):
        if not self.settings['port']:
            raise ValueError('Выберите COM-порт в меню «Настройки → COM-порт и опрос».')
        import serial
        log = Journal("fpga", self.settings, self.log_base)
        self.publish("log", path=str(log.folder))
        port = serial.Serial()
        port.port, port.baudrate = self.settings["port"], self.settings["baud"]
        port.bytesize, port.parity, port.stopbits = self.settings["bits"], self.settings["parity"], self.settings["stop_bits"]
        port.timeout, port.write_timeout = .002, .1
        port.dtr = port.rts = False
        freshness = Freshness()
        client = None
        active = None
        count = timeouts = 0
        try:
            self.publish("status", message=f"Подключение к {port.port}…")
            port.open()
            wire = InterruptiblePort(port, self.stop_event, log)
            self.publish("status", message=f"{port.port} · UART v3 · подключено")
            with (log.folder / "uart.bin").open("wb") as raw, (log.folder / "measurements.csv").open("w", newline="", encoding="utf-8") as f:
                client = ConfigurationClient(wire, self.settings['fpga_timeout_ms']/1000, raw_file=raw)
                writer = None
                if self.polling:
                    active = self.config_operation(client, log, 'connect', None)
                while not self.stop_event.is_set():
                    try:
                        action, channels = self.commands.get_nowait()
                    except queue.Empty:
                        action = None
                    if action:
                        active = self.config_operation(client, log, action, channels)
                        freshness = Freshness()
                        raw.flush()
                        continue
                    if not self.polling:
                        break
                    begin = time.monotonic()
                    try:
                        row = client.request()
                        received = time.monotonic()
                        if not row.get("measurement"):
                            raise RuntimeError(f"FPGA отклонила запрос: {row.get('status_name')}")
                        freshness.check(row)
                        # A new generation may originate from another host or a board reset.
                        if not active or active['generation'] != row['generation'] or active['configuring']:
                            active = self.config_operation(client, log, 'refresh', None)
                        row['dds_channels'] = (deepcopy(active['channels']) if active and
                            active['generation'] == row['generation'] and not active['configuring'] else None)
                        for band in ('high', 'low'):
                            row[f'expected_{band}_frequency_hz'] = row[f'delta_{band}'] * 500_000_000 / 2**32
                        if row['configuring']:
                            row['valid'] = False
                            for key in list(row):
                                if key.startswith(('analog_', 'digital_')) and key.endswith('_valid'):
                                    row[key] = False
                                if key.endswith('_deg') and not key.endswith('_raw_deg'):
                                    row[key] = None
                        count += 1
                        row['monotonic'] = received
                        row['request_started'] = begin
                        row['roundtrip_ms'] = 1000*(received-begin)
                        if writer is None:
                            # Preserve every decoded field, including validity/raw values.
                            writer = csv.DictWriter(f, fieldnames=list(row))
                            writer.writeheader()
                        writer.writerow(dict(row, dds_channels=json.dumps(row['dds_channels'])))
                        f.flush()
                        raw.flush()
                        self.emit(dict(source='fpga', kind='sample', monotonic=received, row=row,
                                       packets=count, timeouts=timeouts, crc=client.decoder.bad_packets,
                                       roundtrip_ms=row['roundtrip_ms'], request_started=begin))
                    except TimeoutError:
                        timeouts += 1
                        log.event("timeout", request_id=client.request_id, timeout_ms=self.settings["fpga_timeout_ms"], bad_packets=client.decoder.bad_packets)
                        self.publish("timeout", message="FPGA v3 не ответила вовремя", timeouts=timeouts, crc=client.decoder.bad_packets)
                    self.stop_event.wait(max(0, self.settings["fpga_interval_ms"] / 1000 - (time.monotonic() - begin)))
        except InterruptedError:
            log.event("requests_stopped")
        except Exception as error:
            log.event("error", error=repr(error))
            raise
        finally:
            port.close()
            log.event("closed", packets=count, timeouts=timeouts, bad_packets=client.decoder.bad_packets if client else 0)
            log.close()

    def config_operation(self, client, log, action, channels):
        self.publish('dds_busy', action=action)
        log.event('dds_start', action=action, channels=channels)
        result, error = None, None
        try:
            result = client.apply(channels) if action == 'apply' else client.read()
            if result['configuring']:
                raise RuntimeError('FPGA ещё применяет настройки. Повторите чтение банка.')
        except InterruptedError:
            raise
        except Exception as exc:
            error = str(exc)
            if action == 'apply':
                # A lost ACK does not prove failure. Never repeat COMMIT automatically.
                try:
                    result = client.read()
                except (TimeoutError, RuntimeError) as read_error:
                    error += '; чтение банка: ' + str(read_error)
        log.event('dds_result', action=action, result=result, error=error)
        self.publish('dds_result', action=action, config=result, error=error)
        return result

    async def run_vector(self):
        if not self.settings['vector_address']:
            raise ValueError('Укажите адрес своей Vector60 в настройках подключения.')
        from bumble.hci import OwnAddressType
        from vector60 import Recorder
        from vector60_winusb import WinUsbVector
        self.loop, self.task = asyncio.get_running_loop(), asyncio.current_task()
        log = Journal("vector60", self.settings, self.log_base)
        self.publish("log", path=str(log.folder))
        client = recorder = None
        attempt = 0
        try:
            while not self.stop_event.is_set():
                attempt += 1
                recorder = Recorder(log.folder / f"connection-{attempt:03d}")
                client = WinUsbVector(recorder)
                client.usb_transport = self.settings['vector_usb_transport']
                self.publish("status", message="Подключение к Vector60…")
                try:
                    await client.open()
                    client.device.connect = partial(client.device.connect, own_address_type=OwnAddressType.PUBLIC)
                    await client.connect(self.settings["vector_address"])
                    self.publish("status", message="Vector60 · опрос запущен")
                    while not self.stop_event.is_set():
                        try:
                            await vector_cycle(client, self.settings, self.publish)
                        except TimeoutError:
                            # Restore the original measurement loop without tearing
                            # down a healthy BLE link. measure() drains old queued
                            # samples before restarting. ATD has no device request ID.
                            log.event("timeout", timeout_s=self.settings["vector_timeout_s"], recovery="restart_poll")
                            self.publish("timeout", message="Vector60: тайм-аут, перезапуск опроса…")
                            await asyncio.sleep(self.settings["vector_interval_s"])
                except TimeoutError:
                    log.event("connection_timeout")
                    self.publish("timeout", message="Vector60: тайм-аут подключения, повтор…")
                except ConnectionError as error:
                    log.event("disconnected", error=str(error))
                    self.publish("timeout", message="Vector60: связь потеряна, переподключение…")
                finally:
                    closing, client = client, None
                    try:
                        if closing:
                            await asyncio.wait_for(closing.close(), 6)
                    finally:
                        recorder.close()
                        recorder = None
                if not self.stop_event.is_set():
                    await asyncio.sleep(self.settings["vector_interval_s"])
        finally:
            try:
                if client:
                    await asyncio.wait_for(client.close(), 6)
            finally:
                if recorder:
                    recorder.close()
                log.event("closed")
                log.close()
                self.loop = self.task = None

    def run_demo(self):
        self.publish("status", message="Демонстрационные данные")
        count = 0
        active = dict(configuration=True, protocol_version=3, configuring=False, generation=0,
                      channels=dds_channels(self.settings['dds']))
        if self.source == 'fpga' and self.polling:
            self.publish('dds_result', action='connect', config=deepcopy(active), error=None)
        start = time.monotonic()
        while not self.stop_event.is_set():
            if self.source == 'fpga':
                try:
                    action, channels = self.commands.get_nowait()
                    if action == 'apply':
                        active['channels'] = channels
                        active['generation'] += 1
                    self.publish('dds_result', action=action, config=deepcopy(active), error=None)
                    continue
                except queue.Empty:
                    if not self.polling:
                        break
            t = time.monotonic() - start
            # Common monotonic clock: both demo workers see stationary plateaus.
            distance = 800 + 400 * (int(time.monotonic() // 12) % 5)
            if self.source == "vector":
                self.publish("sample", distance_mm=distance)
                self.stop_event.wait(max(.2, self.settings["vector_interval_s"]))
                continue
            count += 1
            high = ((-distance * .1795 + 2 * math.sin(t / 3) + 180) % 360) - 180
            low = distance * .00332 + .3 * math.sin(t)
            row = dict(valid=True, fresh=True, protocol_version=3, generation=active['generation'], configuring=False,
                       dds_channels=deepcopy(active['channels']), sequence=count, sample_index=count * 250,
                       digital_sequence=count, adc_ok=255, flags=3, digital_flags=3,
                       diagnostics=0, beam_lost=False, digital_age_ms=1,
                       analog_high_deg=high, analog_low_deg=low,
                       digital_high_deg=high + .15, digital_low_deg=low + .2)
            for pair, value in (("high", high), ("low", low)):
                for edge in ("rise", "fall"):
                    row[f"digital_{pair}_{edge}_deg"] = value
                a, b = (1, 3) if pair == 'high' else (2, 0)
                delta = active['channels'][a]['ftw'] - active['channels'][b]['ftw']
                row[f'delta_{pair}'] = delta
                row[f'expected_{pair}_frequency_hz'] = delta * 500_000_000 / 2**32
                row[f"digital_{pair}_frequency_hz"] = row[f'expected_{pair}_frequency_hz'] + math.sin(t)
                row[f'digital_{pair}_period_ticks'] = round(125_000_000/row[f"digital_{pair}_frequency_hz"])
            for i in range(1, 9):
                row[f"adc{i}_v"], row[f"adc{i}_raw"] = .3 * i, 32768 + 800 * i
                if i <= 4:
                    row[f"ch{i}_peak_v"] = i * .4 + .02 * math.sin(t)
                    row[f"detector{i}_v"] = i * .25
            self.publish("sample", row=row, packets=count, timeouts=0, crc=0, roundtrip_ms=13,
                         request_started=time.monotonic()-.013)
            self.stop_event.wait(max(.02, self.settings["fpga_interval_ms"] / 1000))


async def vector_cycle(client, settings, publish):
    """Original ATK retry cadence; next cycle waits for the reply and interval."""
    timeout = settings["vector_timeout_s"]
    sample = await asyncio.wait_for(client.measure(timeout=timeout, repeat_interval=1.0), timeout=timeout)
    publish("sample", distance_mm=sample["distance_m"] * 1000)
    await asyncio.sleep(settings["vector_interval_s"])

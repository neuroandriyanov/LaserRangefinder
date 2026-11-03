"""UART v3 integration fixtures: no real COM or Bluetooth access."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from .model import (DEFAULTS, LEGACY_DDS, PROFILE_CHANNELS, ROOT, SettingsStore,
                    dds_channels, dds_rows)
from .workers import DeviceWorker
from .distance import estimate_distance, fit_calibration
from .test_distance import synthetic_points, sample
from fpga_config import validate
from fpga_measurements import crc16
from test_fpga_measurements import telemetry, seal


class FakeV3Port:
    def __init__(self, drop_commit=False, reject_word=None):
        self.data = b''
        self.closed = False
        self.writes = []
        self.channels = deepcopy(PROFILE_CHANNELS)
        self.generation = self.reads = 0
        self.drop_commit, self.reject_word = drop_commit, reject_word

    def open(self):
        self.asserted = (self.port, self.baudrate, self.bytesize, self.parity,
                         self.stopbits, self.dtr, self.rts)

    @property
    def in_waiting(self):
        return len(self.data)

    def write(self, frame):
        assert frame[2] == 3 and crc16(frame[2:-2]) == int.from_bytes(frame[-2:], 'little')
        self.writes.append(frame)
        cmd, param, request, value = struct.unpack_from('<BBHH', frame, 4)
        if cmd == 2 and param == 1:
            p = bytearray(48)
            p[:12] = struct.pack('<2s6BHH', b'\xa5\x5a', 3, 48, 0x82, 0, 128, 0, request, self.generation)
            p[12:44] = validate(self.channels)
        elif cmd == 2:
            self.reads += 1
            p = bytearray(telemetry(request, self.reads, self.reads*250, self.reads)[:88]) + bytearray(24)
            p[2:4] = bytes((3, 112))
            dh = self.channels[1]['ftw']-self.channels[3]['ftw']
            dl = self.channels[2]['ftw']-self.channels[0]['ftw']
            struct.pack_into('<IIBBHII', p, 88, round(2**30/dh), round(2**30/dl), 1, 0, self.generation, dh, dl)
        else:
            status = 4
            if param == 0xf0:
                self.stage = bytearray(32)
            elif 0x10 <= param <= 0x1f:
                struct.pack_into('<H', self.stage, (param-0x10)*2, value)
                if param == self.reject_word:status = 3
            elif param == 0xf1:
                self.channels = [dict(zip(('ftw','phase_word','amplitude'), struct.unpack_from('<IHH',self.stage, i*8))) for i in range(4)]
                self.generation += 1
                if self.drop_commit:
                    return len(frame)
                status = 0
            p = bytearray(struct.pack('<2s6BH', b'\xa5\x5a',3,12,0x81,status,param,0,request)+b'\0\0')
        self.data += seal(p)
        return len(frame)

    def read(self, size):
        data, self.data = self.data[:size], self.data[size:]
        return data

    def close(self):
        self.closed = True


class V3AppTests(unittest.TestCase):
    def test_defaults_exactly_match_selected_profile(self):
        saved = json.loads((ROOT/'profiles/dds/default.json').read_text(encoding='utf-8'))
        self.assertEqual(dds_channels(DEFAULTS['dds']), saved['channels'])
        for rows in (DEFAULTS['dds'], [{k:format(v,'.12g') for k,v in r.items()} for r in DEFAULTS['dds']]):
            self.assertEqual(dds_channels(rows), PROFILE_CHANNELS)

    def test_schema_migration_preserves_custom_values_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder)/'settings.json')
            old = dict(deepcopy(DEFAULTS), schema=1,
                       dds=[{k:float(format(v,'.12g')) for k,v in r.items()} for r in LEGACY_DDS], port='COM17')
            store.path.write_text(json.dumps(old), encoding='utf-8')
            before = store.path.read_bytes()
            loaded, warning = store.load()
            self.assertTrue(warning)
            self.assertEqual(loaded['dds'], DEFAULTS['dds'])
            self.assertEqual(loaded['port'], 'COM17')
            self.assertEqual(store.path.read_bytes(), before)
            store.save(loaded)
            self.assertEqual(next(Path(folder).glob('*before-v3*.json')).read_bytes(), before)
            old['dds'][0]['phase_deg'] = 90
            store.path.write_text(json.dumps(old), encoding='utf-8')
            self.assertEqual(store.load()[0]['dds'], old['dds'])

    def test_if_boundaries_validate_quantized_words(self):
        for diff, good in ((8589,False),(8590,True),(171799,True),(171800,False),(-34360,False)):
            channels = deepcopy(PROFILE_CHANNELS)
            channels[2]['ftw'] = channels[0]['ftw']+diff
            if good:self.assertEqual(dds_channels(dds_rows(channels)),channels)
            else:
                with self.assertRaises(ValueError):dds_channels(dds_rows(channels))

    def run_command(self, port, channels):
        events = []
        with tempfile.TemporaryDirectory() as folder, patch('serial.Serial',return_value=port):
            worker = DeviceWorker('fpga',dict(DEFAULTS,port='COM_TEST',fpga_timeout_ms=30),events.append,log_base=folder,polling=False)
            worker.submit('apply',channels)
            worker.start();worker.thread.join(3)
            self.assertFalse(worker.alive)
            self.assertTrue(port.closed)
            self.assertTrue(next(Path(folder).rglob('uart.bin')).stat().st_size)
        return next(e for e in events if e['kind']=='dds_result')

    def test_one_shot_sends_every_word_once_and_confirms_readback(self):
        port = FakeV3Port()
        wanted = deepcopy(PROFILE_CHANNELS)
        wanted[0].update(phase_word=4096,amplitude=230)
        wanted[1]['ftw'] += 100
        result = self.run_command(port,wanted)
        self.assertIsNone(result['error'])
        self.assertEqual(result['config']['channels'],wanted)
        self.assertEqual([f[5] for f in port.writes],[0xf0,*range(0x10,0x20),0xf1,1])
        self.assertEqual(port.reads,0)

    def test_lost_commit_ack_reads_bank_without_repeating_update(self):
        port = FakeV3Port(drop_commit=True)
        result = self.run_command(port,PROFILE_CHANNELS)
        self.assertTrue(result['error'])
        self.assertEqual(result['config']['channels'],PROFILE_CHANNELS)
        self.assertEqual(port.generation,1)
        self.assertEqual(sum(f[5]==0xf1 for f in port.writes),1)

    def test_rejected_stage_does_not_commit(self):
        port = FakeV3Port(reject_word=0x14)
        result = self.run_command(port,PROFILE_CHANNELS)
        self.assertTrue(result['error'])
        self.assertEqual(port.generation,0)
        self.assertFalse(any(f[5]==0xf1 for f in port.writes))

    def test_apply_between_polls_has_no_interleaved_measurement(self):
        events=[];port=FakeV3Port()
        def emit(event):
            events.append(event)
            if event['kind']=='sample':
                if event['packets']==1:worker.submit('apply',PROFILE_CHANNELS)
                else:worker.stop()
        with tempfile.TemporaryDirectory() as folder,patch('serial.Serial',return_value=port):
            worker=DeviceWorker('fpga',dict(DEFAULTS,port='COM_TEST'),emit,log_base=folder)
            worker.start();worker.thread.join(3)
            self.assertFalse(worker.alive)
            header=next(Path(folder).rglob('measurements.csv')).read_text(encoding='utf-8').splitlines()[0]
            for key in ('generation','delta_low','analog_high_raw_deg','ch4_peak_counts','adc8_raw','digital_low_period_ticks','dds_channels'):
                self.assertIn(key,header)
        start=next(i for i,f in enumerate(port.writes) if f[5]==0xf0)
        self.assertEqual([f[4] for f in port.writes[start:start+18]],[1]*18)
        rows=[e['row'] for e in events if e['kind']=='sample']
        self.assertEqual([r['generation'] for r in rows],[0,1])
        self.assertTrue(all(r['dds_channels']==PROFILE_CHANNELS for r in rows))

    def test_distance_rejects_unknown_unbound_or_mismatched_dds(self):
        points=synthetic_points()
        model=fit_calibration(points,confirmed_dds=PROFILE_CHANNELS)
        row=dict(sample(1600),protocol_version=3,dds_channels=deepcopy(PROFILE_CHANNELS))
        self.assertTrue(estimate_distance(model,row)['valid'])
        row['dds_channels'][0]['phase_word']=1
        self.assertEqual(estimate_distance(model,row)['reason'],'dds_mismatch')
        row['dds_channels']=None
        self.assertEqual(estimate_distance(model,row)['reason'],'dds_unknown')
        row['dds_channels']=PROFILE_CHANNELS
        self.assertEqual(estimate_distance(fit_calibration(points),row)['reason'],'dds_unbound')


if __name__=='__main__':unittest.main()

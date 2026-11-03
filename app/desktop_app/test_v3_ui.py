"""Actual Tk callbacks with a simulated serial instrument and isolated settings."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from .model import SettingsStore, PROFILE_CHANNELS, ROOT, dds_channels
from .ui import App
from .test_v3 import FakeV3Port
from .test_calibration import row
from .test_cal2 import write_provenance_fixture
from .calibration import load_csv_points


class V3UITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = tk.Tk();self.root.withdraw()
        self.app = App(self.root, SettingsStore(Path(self.folder.name)/'settings.json'), log_base=self.folder.name)
        self.app.settings['port'] = 'COM_TEST'

    def tearDown(self):
        self.app.close()
        deadline=time.monotonic()+3
        while any(w and w.alive for w in self.app.workers.values()) and time.monotonic()<deadline:
            self.root.update();time.sleep(.01)
        self.folder.cleanup()

    def drain(self):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            self.root.update()
            worker=self.app.workers['fpga']
            if worker and not worker.alive and self.app.events.empty():return
            time.sleep(.01)
        self.fail('GUI operation did not finish')

    def test_apply_without_polling_then_read_does_not_overwrite_draft(self):
        port=FakeV3Port()
        with patch('serial.Serial',return_value=port):
            self.app.dds_vars[0]['phase_deg'].set('90')
            self.app.dds_vars[3]['amplitude'].set('430')
            self.app.apply_dds();self.drain()
            wanted=deepcopy(PROFILE_CHANNELS)
            wanted[0]['phase_word']=4096;wanted[3]['amplitude']=430
            self.assertEqual(self.app.active_config['channels'],wanted)
            self.assertEqual(dds_channels(self.app.store.load()[0]['dds']),wanted)
            self.assertIn('совпал',self.app.dds_message.get())
            self.assertFalse(self.app.workers['fpga'].polling)
            self.assertTrue(port.closed)
            self.app.dds_vars[0]['phase_deg'].set('180')
            self.app.dds_command('read');self.drain()
            self.assertEqual(self.app.dds_vars[0]['phase_deg'].get(),'180')
            self.assertEqual(self.app.active_config['channels'][0]['phase_word'],4096)
            self.assertEqual(str(self.app.dds_apply_button['state']),'normal')

    def test_invalid_if_has_no_worker_or_serial_side_effect(self):
        self.app.dds_vars[2]['frequency_mhz'].set('1')
        with patch('serial.Serial',side_effect=AssertionError('Unexpected port open')),patch('desktop_app.ui.messagebox.showerror'):
            self.app.apply_dds()
        self.assertIsNone(self.app.workers['fpga'])
        self.assertIn('ПЧ НЧ',self.app.dds_message.get())
        self.app.restore_dds_profile()

    def test_if_fields_are_readonly_and_follow_frequency_edits(self):
        for entry in self.app.dds_if_entries.values():
            self.assertEqual(str(entry['state']),'readonly')
        self.assertEqual(self.app.dds_if_vars['low'].get(),'4000.030458')
        self.app.dds_vars[2]['frequency_mhz'].set(str(float(self.app.dds_vars[2]['frequency_mhz'].get())+.001))
        self.assertAlmostEqual(float(self.app.dds_if_vars['low'].get()),5000.038072,places=5)
        self.app.dds_vars[2]['frequency_mhz'].set('invalid')
        self.assertEqual(self.app.dds_if_vars['low'].get(),'—')
        self.app.restore_dds_profile()

    def test_cal2_import_calculate_and_live_row_use_verified_bank(self):
        write_provenance_fixture(Path(self.folder.name)/'calibration',load_csv_points(ROOT/'desktop_app/cal2.csv'))
        with patch('desktop_app.calibration_view.filedialog.askopenfilename',return_value=str(ROOT/'desktop_app/cal2.csv')):
            self.app.calibration.import_csv()
        self.assertEqual(self.app.calibration.store.metadata['dds_channels'],PROFILE_CHANNELS)
        self.app.calibration.calculate()
        self.assertEqual(self.app.distance_model['dds_channels'],PROFILE_CHANNELS)
        point=self.app.calibration.collector.points[10]
        self.app.handle(dict(source='fpga',kind='sample',monotonic=time.monotonic(),packets=1,crc=0,timeouts=0,
                             row=dict(valid=True,fresh=True,protocol_version=3,dds_channels=PROFILE_CHANNELS,**point['phases'])))
        self.app.render_values()
        self.assertEqual(self.app.card_vars['phase_distance_mm'].get(),'2884 мм')

    def test_three_pairs_save_bank_and_emit_sound_only_after_third(self):
        cal=self.app.calibration
        cal.create_store();cal.collector.start(0)
        with patch.object(cal,'beep') as beep:
            for i in range(3):
                stamp=float(i+1)
                cal.handle(dict(source='vector',kind='sample',monotonic=stamp,distance_mm=1642))
                cal.handle(dict(source='fpga',kind='sample',monotonic=stamp+.02,request_started=stamp+.005,
                                row=dict(row(),protocol_version=3,generation=81,dds_channels=PROFILE_CHANNELS)))
                self.assertEqual(beep.call_count,int(i==2))
            self.assertEqual(len(cal.collector.points[0]['observations']),3)
            self.assertEqual(cal.store.metadata['dds_channels'],PROFILE_CHANNELS)
            changed=deepcopy(PROFILE_CHANNELS);changed[0]['amplitude']+=1
            cal.handle(dict(source='fpga',kind='sample',monotonic=4,request_started=3.99,
                            row=dict(row(),protocol_version=3,generation=82,dds_channels=changed)))
            self.assertFalse(cal.collector.running)
            self.assertIn('Настройки DDS изменились',cal.progress.get())


if __name__=='__main__':unittest.main()

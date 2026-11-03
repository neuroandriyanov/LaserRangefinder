"""Hidden Tk integration checks; all packets are fixtures, no device workers run."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from .calibration import load_csv_points
from .distance import DistanceStore
from .model import ROOT, SettingsStore

os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
from .ui import App


class DistanceUITests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=SettingsStore(Path(self.folder.name)/'settings.json')
        self.root=tk.Tk();self.root.withdraw()
        self.app=App(self.root,self.store)
        self.points=load_csv_points(ROOT/'desktop_app/cal2.csv')
        self.app.calibration.collector.points=deepcopy(self.points)
        self.app.calibration.calculate()

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def packet(self, point=10, **changes):
        row=dict(valid=True,fresh=True,beam_lost=False,diagnostics=4,**self.points[point]['phases'])
        row.update(changes)
        return dict(source='fpga',kind='sample',monotonic=time.monotonic(),row=row,packets=1,crc=0,timeouts=0)

    def test_calculate_callback_persists_and_startup_restores_without_points(self):
        self.assertIsNotNone(self.app.distance_model)
        saved=self.app.distance_model
        restored,warning=DistanceStore(self.store.path).load()
        self.assertFalse(warning);self.assertEqual(saved,restored)
        self.app.close()
        self.root=tk.Tk();self.root.withdraw()
        self.app=App(self.root,self.store)
        self.assertEqual(self.app.distance_model,saved)
        self.assertEqual(len(self.app.calibration.collector.points),0)
        self.assertIn('21',self.app.calibration.calculation_text.get())

    def test_new_card_table_and_history_use_calculated_distance_and_invalidate(self):
        event=self.packet();raw=deepcopy(event['row'])
        self.app.handle(event);self.app.render_values()
        self.assertEqual(event['row'],raw)
        self.assertEqual(self.app.card_vars['phase_distance_mm'].get(),'2884 мм')
        self.assertAlmostEqual(float(self.app.table.set('phase_distance_mm','value')),2883.808,places=3)
        self.assertIsNotNone(self.app.history.fpga[-1][1]['phase_distance_mm'])
        self.app.handle(self.packet(fresh=False));self.app.render_values()
        self.assertEqual(self.app.card_vars['phase_distance_mm'].get(),'—')
        self.assertIsNone(self.app.history.fpga[-1][1]['phase_distance_mm'])
        self.app.handle(self.packet());self.app.render_values()
        self.app.handle(dict(source='fpga',kind='timeout',monotonic=time.monotonic(),message='fixture timeout'))
        self.app.render_values()
        self.assertEqual(self.app.card_vars['phase_distance_mm'].get(),'—')
        self.app.handle(self.packet(analog_low_deg=45));self.app.render_values()
        self.assertEqual(self.app.card_vars['phase_distance_mm'].get(),'—')

    def test_failed_recalculation_preserves_active_and_saved_model(self):
        old=deepcopy(self.app.distance_model)
        disk=self.app.distance_store.path.read_bytes()
        with patch('desktop_app.distance.os.replace',side_effect=OSError('fixture disk error')):
            self.app.calibration.calculate()
        self.assertEqual(self.app.distance_model,old)
        self.assertEqual(self.app.distance_store.path.read_bytes(),disk)
        self.assertIn('Расчёт не применён',self.app.calibration.calculation_text.get())


if __name__=='__main__':unittest.main()

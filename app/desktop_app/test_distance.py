"""Distance regression, branch guards and restart/atomic persistence behavior."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from .calibration import load_csv_points
from .distance import DistanceStore, estimate_distance, fit_calibration, points_digest, wrap, LEGACY_METHOD
from .model import History, ROOT, SettingsStore, DEFAULTS


def synthetic_points():
    points = []
    for index, distance in enumerate(np.linspace(600, 5700, 23), 1):
        phases = {}
        for channel, offset in (('analog', 0), ('digital', 1.8)):
            high = wrap(-11.0 - .180 * distance + offset)
            low = 4.7 + .00356 * distance - 2.1 * math.sin(math.radians(high)) - .57 * math.cos(math.radians(high))
            phases.update({f'{channel}_high_deg':float(high), f'{channel}_low_deg':float(low)})
        points.append(dict(index=index, distance_mm=float(distance), phases=phases))
    return points


def sample(distance):
    high = wrap(-11 - .180 * distance)
    low = 4.7 + .00356 * distance - 2.1 * math.sin(math.radians(high)) - .57 * math.cos(math.radians(high))
    return dict(valid=True, fresh=True, beam_lost=False, analog_high_deg=high, analog_low_deg=low)


class DistanceTests(unittest.TestCase):
    def setUp(self):
        self.points = synthetic_points()
        self.model = fit_calibration(self.points)

    def test_current_cal1_matches_research_coefficients_and_predictions(self):
        folder = ROOT/'tests/fixtures/cal1'
        points = load_csv_points(folder/'cal1.csv')
        before = deepcopy(points)
        model = fit_calibration(points,method=LEGACY_METHOD)
        research = json.loads((folder/'coefficients.json').read_text(encoding='utf-8'))['profiles']
        for channel in ('analog','digital'):
            for name in ('high_forward_deg_per_m','low_harmonic_deg_per_m'):
                np.testing.assert_allclose(model['profiles'][channel][name],research[channel][name],atol=1e-9,rtol=0)
            np.testing.assert_allclose(model['profiles'][channel]['cubic_mm'],research[channel]['fine_coefficients_mm']['cubic'],atol=1e-8,rtol=0)
        for p in points:
            result = estimate_distance(model,dict(valid=True,fresh=True,**p['phases']))
            self.assertTrue(result['valid'])
            self.assertLess(abs(result['distance_mm']-p['distance_mm']),15.1)
        self.assertEqual(points,before)

    def test_unseen_positions_across_multiple_turns(self):
        for distance in (777,943,1943,2943,3943,4943,5555):
            result=estimate_distance(self.model,sample(distance))
            self.assertTrue(result['valid'])
            self.assertAlmostEqual(result['distance_mm'],distance,places=6)

    def test_signed_wrap_and_equivalent_angle_representation(self):
        center=(180-11)/.180
        results=[estimate_distance(self.model,sample(center+delta))['distance_mm'] for delta in (-.001,.001)]
        self.assertAlmostEqual(results[1]-results[0],.002,places=6)
        row=sample(1234);row['analog_high_deg']%=360
        self.assertAlmostEqual(estimate_distance(self.model,row)['distance_mm'],1234,places=6)

    def test_invalid_stale_beam_lost_and_individual_channel_validity(self):
        for change in ({'valid':False},{'fresh':False},{'beam_lost':True},{'analog_high_valid':False},
                       {'analog_low_valid':False},{'analog_high_deg':float('nan')},{'analog_low_deg':float('inf')}):
            result=estimate_distance(self.model,dict(sample(3000),**change))
            self.assertFalse(result['valid']);self.assertIsNone(result['distance_mm'])
        self.assertEqual(estimate_distance(None,sample(3000))['reason'],'not_calibrated')

    def test_extrapolation_and_ambiguous_period_are_not_valid_distance(self):
        self.assertEqual(estimate_distance(self.model,sample(8000))['reason'],'outside_calibration')
        row=sample(3000);row['analog_low_deg']+=3.56
        self.assertEqual(estimate_distance(self.model,row)['reason'],'ambiguous_branch')

    def test_reordered_calibration_points_and_identity(self):
        reversed_points=self.points[::-1]
        model=fit_calibration(reversed_points)
        self.assertEqual(points_digest(self.points),points_digest(reversed_points))
        self.assertAlmostEqual(estimate_distance(model,sample(2500))['distance_mm'],2500,places=6)

    def test_reject_insufficient_duplicate_nonfinite_and_narrow_points(self):
        bad_cases=[self.points[:7],[*self.points,self.points[0]],deepcopy(self.points),self.points[:8]]
        bad_cases[2][3]['phases']['analog_low_deg']=float('nan')
        for points in bad_cases:
            with self.assertRaises(ValueError):fit_calibration(points)

    def test_restart_uses_saved_coefficients_without_points_file(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=SettingsStore(Path(folder)/'custom.json');settings.save(DEFAULTS)
            before=settings.path.read_bytes()
            store=DistanceStore(settings.path)
            store.save(self.model)
            restored, warning=DistanceStore(settings.path).load()
            self.assertFalse(warning)
            self.assertEqual(restored,self.model)
            self.assertAlmostEqual(estimate_distance(restored,sample(4321))['distance_mm'],4321,places=6)
            self.assertEqual(settings.path.read_bytes(),before)

    def test_atomic_save_failure_keeps_previous_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DistanceStore(Path(folder)/'settings.json');store.save(self.model)
            original=store.path.read_bytes()
            replacement=fit_calibration(self.points,source='another series')
            with patch('desktop_app.distance.os.replace',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):store.save(replacement)
            self.assertEqual(store.path.read_bytes(),original)
            self.assertEqual(store.load()[0]['id'],self.model['id'])

    def test_damaged_coefficients_and_demo_mismatch_are_not_applied(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DistanceStore(Path(folder)/'settings.json');store.save(self.model)
            self.assertIsNone(DistanceStore(Path(folder)/'settings.json',demo=True).load()[0])
            altered=deepcopy(self.model);altered['profiles']['analog']['fine_mm'][0]+=100
            store.path.write_text(json.dumps(altered),encoding='utf-8')
            original=store.path.read_bytes()
            loaded,warning=store.load()
            self.assertIsNone(loaded);self.assertTrue(warning)
            self.assertEqual(store.path.read_bytes(),original)

    def test_graph_breaks_invalid_distance_but_preserves_amplitude(self):
        history=History()
        history.add_fpga(1,dict(valid=True,fresh=True,phase_distance_valid=True,phase_distance_mm=2500,adc_ok=255,ch3_peak_v=.2))
        history.add_fpga(2,dict(valid=True,fresh=True,phase_distance_valid=False,phase_distance_mm=2500,adc_ok=255,ch3_peak_v=.1))
        self.assertTrue(math.isnan(history.series('phase_distance_mm','time',60)[1][-1]))
        self.assertEqual(history.series('ch3_peak_v','time',60)[1],[.2,.1])


if __name__=='__main__':unittest.main()

"""Cal2 regression, provenance and independent omitted-position checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from .model import ROOT, PROFILE_CHANNELS, DEFAULTS, dds_intermediate_frequencies
from .calibration import CalibrationStore, load_csv_points, verified_csv_source
from .distance import fit_calibration, estimate_distance, predict_profile, DistanceStore, LEGACY_METHOD


def write_provenance_fixture(directory, points):
    """Synthetic protocol records for tests; never presented as bench evidence."""
    recorded = deepcopy(points)
    for point in recorded:
        point.pop('origin', None)
        point['observations'] = [dict(fpga=dict(valid=True, fresh=True,
            dds_channels=deepcopy(PROFILE_CHANNELS), **point['phases'])) for _ in range(3)]
    path = Path(directory)/'fixture'/ 'points.json'
    CalibrationStore(path, dict(demo=False, required_samples=3,
        dds_channels=PROFILE_CHANNELS, test_fixture=True)).save(recorded)
    return path


class Cal2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.points=load_csv_points(ROOT/'desktop_app/cal2.csv')
        cls.model=fit_calibration(cls.points,confirmed_dds=PROFILE_CHANNELS)

    def test_raw_provenance_must_match_every_point_and_timestamp(self):
        source=ROOT/'desktop_app/cal2.csv';before=hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            path=write_provenance_fixture(folder,self.points)
            result=verified_csv_source(self.points,folder)
            self.assertEqual(result['dds_channels'],PROFILE_CHANNELS)
            self.assertEqual(result['verified_series_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            bad=deepcopy(self.points);bad[1]['phases']['analog_high_deg']+=.0001
            self.assertEqual(verified_csv_source(bad,folder),{})
            bad=deepcopy(self.points);bad[1]['utc']='unknown'
            self.assertEqual(verified_csv_source(bad,folder),{})
            data=json.loads(path.read_text(encoding='utf-8'))
            data['points'][0]['observations'][0]['fpga']['dds_channels'][0]['amplitude']+=1
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(verified_csv_source(self.points,folder),{})
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)

    def test_original_data_fit_and_monotonic_continuous_distance(self):
        for channel,expected in (('analog',6.798859152518),('digital',7.513619137274)):
            p=self.model['profiles'][channel]
            self.assertAlmostEqual(p['fit_rms_mm'],expected,places=7)
            x=np.linspace(*p['x_range_turns'],3001)
            fine=np.polynomial.polynomial.polyval((x-p['x_center_turns'])/p['x_scale_turns'],p['fine_mm'])
            self.assertTrue(np.all(np.diff(fine)>0))
            # Generate LF from the branch selector; all wrapped high-phase boundaries are traversed.
            a,b=p['high_forward_deg_per_m'];la,lb=p['low_linear_deg_per_m']
            actual=np.array([predict_profile(p,-360*xx,la+lb*((-360*xx-a)/b))[0] for xx in x])
            np.testing.assert_allclose(actual,fine,atol=1e-9)

    def test_low_phase_chooses_branch_without_changing_fine_distance(self):
        point=self.points[10]
        base=dict(valid=True,fresh=True,protocol_version=3,dds_channels=PROFILE_CHANNELS,**point['phases'])
        expected=estimate_distance(self.model,base)['distance_mm']
        for delta in (-.5,0,.5):
            result=estimate_distance(self.model,dict(base,analog_low_deg=base['analog_low_deg']+delta))
            self.assertTrue(result['valid']);self.assertEqual(result['distance_mm'],expected)
        self.assertFalse(estimate_distance(self.model,dict(base,analog_low_deg=base['analog_low_deg']+3.59))['valid'])

    def test_omitted_points_refit_both_models(self):
        errors=[]
        for i in range(1,len(self.points)-1):
            train=self.points[:i]+self.points[i+1:]
            model=fit_calibration(train,confirmed_dds=PROFILE_CHANNELS)
            sample=dict(valid=True,fresh=True,protocol_version=3,dds_channels=PROFILE_CHANNELS,**self.points[i]['phases'])
            result=estimate_distance(model,sample)
            self.assertTrue(result['valid'])
            errors.append(result['distance_mm']-self.points[i]['distance_mm'])
        self.assertAlmostEqual(float(np.sqrt(np.mean(np.square(errors)))),8.518977109188,places=6)

    def test_old_models_load_and_new_models_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DistanceStore(Path(folder)/'settings.json')
            old=fit_calibration(self.points,method=LEGACY_METHOD)
            for model in (old,self.model):
                store.save(model)
                restored,warning=store.load()
                self.assertFalse(warning);self.assertEqual(restored,model)

    def test_if_preview_depends_on_quantized_frequencies_only(self):
        rows=deepcopy(DEFAULTS['dds'])
        self.assertAlmostEqual(dds_intermediate_frequencies(rows)['low'],4000.03045797348)
        rows[1]['amplitude']='bad';rows[2]['phase_deg']='bad'
        self.assertAlmostEqual(dds_intermediate_frequencies(rows)['high'],6749.993190169334)
        rows[1]['frequency_mhz']='not a number'
        with self.assertRaises(ValueError):dds_intermediate_frequencies(rows)


if __name__=='__main__':unittest.main()

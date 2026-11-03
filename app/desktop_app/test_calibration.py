"""Behavior tests for stationary points, timestamp pairing and durable storage."""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .calibration import CalibrationCollector, CalibrationStore, PHASE_KEYS, load_csv_points, distance_code


def row(phase=10):
    return dict(valid=True,fresh=True,diagnostics=4,sequence=123,
                **{key:phase+i for i,key in enumerate(PHASE_KEYS)})


def pair(collector, stamp, distance=1234.5, phase=10):
    collector.vector(stamp,distance)
    return collector.fpga(stamp+.02,stamp+.005,row(phase))


def three(collector,start=1,distance=1234.5):
    result=None
    for i in range(3):result=pair(collector,start+i,distance,phase=10+i)
    return result


class CalibrationTests(unittest.TestCase):
    def test_legacy_five_observation_file_loads_unchanged(self):
        c=CalibrationCollector();c.start(0)
        point=three(c)
        point['observations'] += deepcopy(point['observations'][:2])
        with tempfile.TemporaryDirectory() as folder:
            store=CalibrationStore(Path(folder)/'legacy.json',{'demo':True})
            store.save([point]);before=store.path.read_bytes()
            self.assertEqual(len(CalibrationStore.load(store.path)[1][0]['observations']),5)
            self.assertEqual(store.path.read_bytes(),before)

    def test_generation_change_restarts_confirmation(self):
        c=CalibrationCollector();c.start(0)
        for i in range(2):
            c.vector(i+1,1642)
            c.fpga(i+1.02,i+1.005,dict(row(),generation=80))
        c.vector(3,1642)
        self.assertIsNone(c.fpga(3.02,3.005,dict(row(),generation=81)))
        self.assertEqual(c.samples,[])

    def test_three_pairs_then_commit_and_no_duplicate_after_return(self):
        c=CalibrationCollector();c.start(0)
        for i in range(2):self.assertIsNone(pair(c,i+1))
        p=pair(c,5,phase=-179)
        self.assertEqual(len(p['observations']),3)
        self.assertEqual(p['phases']['analog_high_deg'],-179)
        self.assertEqual(len(c.points),0)  # persistence must happen before commit/sound
        c.commit(p)
        self.assertIsNone(three(c,10))
        q=three(c,20,1500);c.commit(q)
        self.assertIsNone(three(c,30,1234.5))
        self.assertEqual([p['distance_mm'] for p in c.points],[1234.5,1500])

    def test_native_resolution_change_resets_without_rounding_to_mm(self):
        c=CalibrationCollector();c.start(0)
        for i in range(2):pair(c,i+1,1000)
        self.assertIsNone(pair(c,5,1000.1))
        self.assertEqual(len(c.samples),1)
        self.assertIsNone(pair(c,6,1000.1))
        self.assertEqual(pair(c,9,1000.1)['distance_mm'],1000.1)
        self.assertEqual(distance_code(1000.10000000001),10001)
        for value in (float('nan'),float('inf'),-1,1000.15):
            with self.assertRaises(ValueError):distance_code(value)

    def test_inflight_get_is_ignored_and_missing_new_get_expires(self):
        c=CalibrationCollector();c.start(0);c.vector(1,1000)
        self.assertIsNone(c.fpga(1.01,.999,row()))
        self.assertEqual(len(c.samples),0)
        self.assertIsNone(c.fpga(1.03,1.015,row()))
        self.assertEqual(len(c.samples),1)
        c.vector(2,1000);c.expire(2.501)
        self.assertEqual(len(c.samples),0)
        self.assertIsNone(c.fpga(2.55,2.51,row()))

    def test_invalid_or_timeout_resets_all_three_and_stop_discards_old_events(self):
        c=CalibrationCollector();c.start(0)
        for i in range(2):pair(c,i+1)
        c.fpga(4.1,4.09,dict(row(),fresh=False))
        self.assertEqual(len(c.samples),0)
        for i in range(2):pair(c,5+i)
        c.reset('timeout')
        self.assertEqual(len(c.samples),0)
        c.stop();self.assertIsNone(pair(c,10))
        c.start(20);self.assertIsNone(pair(c,19))
        self.assertEqual(len(c.samples),0)

    def test_duplicate_vector_event_is_not_another_measurement(self):
        c=CalibrationCollector();c.start(0)
        pair(c,1)
        for _ in range(3):pair(c,1)
        self.assertEqual(len(c.samples),1)

    def test_restore_session_and_atomic_failure_preserves_old_points(self):
        c=CalibrationCollector();c.start(0);point=three(c)
        with tempfile.TemporaryDirectory() as folder:
            store=CalibrationStore(Path(folder)/'points.json',{'demo':True,'required_samples':3})
            store.save([point]);c.commit(point)
            original=store.path.read_bytes()
            next_point=three(c,10,1500)
            with patch('desktop_app.calibration.os.replace',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):store.save([*c.points,next_point])
            self.assertEqual(store.path.read_bytes(),original)
            self.assertEqual(len(c.points),1)
            restored,points=CalibrationStore.load(store.path)
            restored_collector=CalibrationCollector(points);restored_collector.start(0)
            self.assertIsNone(three(restored_collector))
            restored.export_csv(Path(folder)/'points.csv',points)
            with (Path(folder)/'points.csv').open(encoding='utf-8-sig') as stream:
                csv_rows=list(csv.DictReader(stream))
            self.assertEqual(float(csv_rows[0]['distance_mm']),1234.5)
            self.assertEqual(len(csv_rows),1)

    def test_import_csv_restores_without_inventing_three_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.csv'
            path.write_text('distance_mm,'+','.join(PHASE_KEYS)+'\n1000,179,10,-179,8\n',encoding='utf-8-sig')
            before=path.read_bytes()
            points=load_csv_points(path)
            self.assertEqual(points[0]['observations'],[])
            store=CalibrationStore(Path(folder)/'points.json',{'demo':False,'imported_csv':str(path)})
            store.save(points)
            self.assertEqual(CalibrationStore.load(store.path)[1],points)
            self.assertEqual(path.read_bytes(),before)
            path.write_text('distance_mm,'+','.join(PHASE_KEYS)+'\n1000,179,10,-179,8\n1000,178,10,-178,8\n',encoding='utf-8')
            with self.assertRaises(ValueError):load_csv_points(path)


if __name__=='__main__':unittest.main()

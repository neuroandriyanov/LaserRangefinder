"""Calibration point collection, CSV import and durable source storage."""
from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

PHASE_KEYS = ('analog_high_deg', 'analog_low_deg', 'digital_high_deg', 'digital_low_deg')
REQUIRED_SAMPLES = 3


def distance_code(distance_mm):
    if not isinstance(distance_mm, (float, int)) or not math.isfinite(distance_mm) or distance_mm < 0:
        raise ValueError('Некорректное расстояние рулетки.')
    # ATD distance is an integer in 0.1 mm units; remove binary float roundoff only.
    code = round(distance_mm * 10)
    if abs(distance_mm * 10 - code) > .0001:
        raise ValueError('Расстояние не соответствует шагу данных рулетки 0,1 мм.')
    return code


class CalibrationCollector:
    def __init__(self, points=()):
        self.points = deepcopy(list(points))
        self.seen = {distance_code(p['distance_mm']) for p in self.points}
        self.running = False
        self.started = 0
        self.pending = None
        self.samples = []
        self.last_vector_stamp = float('-inf')
        self.message = 'Нажмите «Старт калибровки».'

    def reset(self, message):
        self.pending = None
        self.samples = []
        self.message = message

    def start(self, stamp):
        self.running = True
        self.started = stamp
        self.last_vector_stamp = float('-inf')
        self.reset('Ожидание трёх одинаковых расстояний…')

    def stop(self, message='Запись точек остановлена.'):
        self.running = False
        self.reset(message)

    def vector(self, stamp, distance_mm):
        if not self.running or stamp < self.started or stamp <= self.last_vector_stamp:
            return
        self.last_vector_stamp = stamp
        try:
            code = distance_code(distance_mm)
        except ValueError as error:
            self.reset(str(error))
            return
        if code in self.seen:
            self.reset(f'{code/10:.1f} мм уже записано. Переместите мишень.')
            return
        if self.pending or self.samples and self.samples[-1]['distance_code'] != code:
            self.reset('Расстояние изменилось; отсчёт начат заново.')
        self.pending = (stamp, code)
        self.message = f'{code/10:.1f} мм · {len(self.samples)}/{REQUIRED_SAMPLES} · ожидание свежих фаз'

    def expire(self, now):
        if self.running and self.pending and now-self.pending[0] > .5:
            self.reset('Нет свежих фаз за 500 мс. Ожидание новой серии из трёх ответов.')

    def fpga(self, stamp, request_started, row):
        if not self.running or stamp < self.started:
            return None
        valid = row.get('valid') and row.get('fresh', False)
        valid = valid and all(isinstance(row.get(key), (int, float)) and math.isfinite(row[key]) for key in PHASE_KEYS)
        if not valid:
            self.reset('Недостоверные фазы. Ожидание новой серии из трёх ответов.')
            return None
        if self.samples and row.get('generation') != self.samples[-1]['fpga'].get('generation'):
            self.reset('Конфигурация DDS обновлена. Ожидание новой серии из трёх ответов.')
            return None
        self.expire(stamp)
        if not self.pending:
            return None
        vector_stamp, code = self.pending
        # Reject an already in-flight GET: the request itself must follow ATD.
        if request_started is None or request_started < vector_stamp or stamp < request_started:
            return None
        self.pending = None
        self.samples.append(dict(distance_code=code, vector_monotonic=vector_stamp,
                                 fpga_request_monotonic=request_started, fpga_receive_monotonic=stamp,
                                 fpga=deepcopy(row)))
        self.message = f'{code/10:.1f} мм · одинаковых показаний {len(self.samples)}/{REQUIRED_SAMPLES}'
        if len(self.samples) < REQUIRED_SAMPLES:
            return None
        point = dict(index=len(self.points)+1, utc=datetime.now(timezone.utc).isoformat(),
                     distance_mm=code/10, phases={key:row[key] for key in PHASE_KEYS},
                     observations=deepcopy(self.samples))
        self.reset('Сохранение точки…')
        return point

    def commit(self, point):
        """Call only after the authoritative file has been atomically saved."""
        code = distance_code(point['distance_mm'])
        if code in self.seen:
            raise ValueError('Это расстояние уже записано.')
        self.points.append(deepcopy(point))
        self.seen.add(code)
        self.message = f'Точка {point["index"]} записана: {point["distance_mm"]:.1f} мм. Переместите мишень.'


class CalibrationStore:
    def __init__(self, path, metadata):
        self.path, self.metadata = Path(path), deepcopy(metadata)

    def save(self, points):
        payload = dict(schema=1, metadata=self.metadata, points=points)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent, delete=False) as output:
                temp = Path(output.name)
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, self.path)
        finally:
            if temp and temp.exists():temp.unlink()

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('schema') != 1 or not isinstance(data.get('points'), list) or not isinstance(data.get('metadata'), dict):
            raise ValueError('Неизвестный формат серии калибровки.')
        seen = set()
        for index, point in enumerate(data['points'], 1):
            code = distance_code(point['distance_mm'])
            imported = point.get('origin') == 'csv' and bool(data['metadata'].get('imported_csv'))
            required = data['metadata'].get('required_samples', 5)
            if required not in (3, 5):
                raise ValueError('Неизвестное число подтверждений точки.')
            if code in seen or point['index'] != index or len(point['observations']) != (0 if imported else required):
                raise ValueError('Некорректная последовательность точек.')
            if not all(isinstance(point['phases'].get(key), (int, float)) and math.isfinite(point['phases'][key]) for key in PHASE_KEYS):
                raise ValueError('В файле нет четырёх корректных фаз.')
            seen.add(code)
        return cls(path, data['metadata']), data['points']

    def export_csv(self, path, points):
        with Path(path).open('w', newline='', encoding='utf-8-sig') as output:
            writer = csv.DictWriter(output, fieldnames=['index','utc','distance_mm',*PHASE_KEYS])
            writer.writeheader()
            for point in points:
                writer.writerow({key:point[key] for key in ('index','utc','distance_mm')} | point['phases'])


def load_csv_points(path):
    """Import the exported columns without fabricating raw observations."""
    points, seen = [], set()
    try:
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not {'distance_mm', *PHASE_KEYS}.issubset(reader.fieldnames or []):
                raise ValueError('CSV должен содержать distance_mm и четыре столбца фаз *_deg.')
            for index, row in enumerate(reader, 1):
                distance = float(row['distance_mm'])
                code = distance_code(distance)
                phases = {key:float(row[key]) for key in PHASE_KEYS}
                if code in seen or not all(math.isfinite(v) for v in phases.values()):
                    raise ValueError(f'Строка {index + 1}: повторное расстояние или некорректная фаза.')
                seen.add(code)
                points.append(dict(index=index, utc=row.get('utc', ''), distance_mm=distance,
                                   phases=phases, observations=[], origin='csv'))
    except (TypeError, KeyError) as error:
        raise ValueError('Некорректные данные CSV.') from error
    if not points:
        raise ValueError('CSV не содержит точек калибровки.')
    return points


def verified_csv_source(points, directory):
    """Recover DDS provenance only from an exact match to recorded observations."""
    expected = sorted(points, key=lambda p:p['distance_mm'])
    matches = []
    for path in sorted(Path(directory).glob('*/points.json')):
        try:
            store, recorded = CalibrationStore.load(path)
            recorded = sorted(recorded, key=lambda p:p['distance_mm'])
            bank = store.metadata.get('dds_channels')
            if not bank or store.metadata.get('demo') or len(recorded) != len(expected):
                continue
            if not all(all(a.get(k) == b.get(k) for k in ('distance_mm','utc','phases'))
                       for a,b in zip(expected,recorded)):
                continue
            if not all(p['observations'] and p['phases'] == {
                    k:p['observations'][-1]['fpga'][k] for k in PHASE_KEYS} for p in recorded):
                continue
            if not all(o['fpga'].get('dds_channels') == bank and o['fpga'].get('valid') and o['fpga'].get('fresh')
                       for p in recorded for o in p['observations']):
                continue
            matches.append(dict(dds_channels=deepcopy(bank),verified_series=str(path.resolve()),
                                verified_series_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not matches or any(m['dds_channels'] != matches[0]['dds_channels'] for m in matches):
        return {}
    return matches[0]

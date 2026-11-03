"""Persistent, bounded distance calibration. Computation runs on the PC, not FPGA."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np

LEGACY_METHOD = 'low_harmonic_high_cubic_v1'
METHOD = 'low_branch_high_quartic_v2'
MIN_POINTS = 8
REASONS = {
    'not_calibrated': 'Нет калибровки',
    'invalid_signal': 'Нет достоверных фаз',
    'ambiguous_branch': 'Неоднозначный период',
    'outside_calibration': 'Вне калибровки',
    'dds_unknown': 'Нет подтверждённого банка DDS',
    'dds_unbound': 'Калибровка не привязана к DDS',
    'dds_mismatch': 'Нужна калибровка для этих DDS',
    'ok': 'Расчёт на ПК · АЦП',
}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def wrap(value):
    return (value + 180.0) % 360.0 - 180.0


def normalized_points(points):
    result = []
    for point in points:
        distance = point['distance_mm']
        phases = point['phases']
        if not finite(distance) or distance < 0 or not all(
                finite(phases.get(f'{channel}_{band}_deg'))
                for channel in ('analog', 'digital') for band in ('high', 'low')):
            raise ValueError('Точки должны содержать расстояние в мм и четыре конечные фазы в градусах.')
        result.append({'distance_mm': float(distance), 'phases': {
            f'{channel}_{band}_deg': float(phases[f'{channel}_{band}_deg'])
            for channel in ('analog', 'digital') for band in ('high', 'low')}})
    result.sort(key=lambda p: p['distance_mm'])
    if any(a['distance_mm'] >= b['distance_mm'] for a, b in zip(result, result[1:])):
        raise ValueError('Для расчёта нужны разные расстояния без повторных точек.')
    return result


def points_digest(points):
    encoded = json.dumps(normalized_points(points), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def solve(matrix, target):
    coef, _, rank, singular = np.linalg.lstsq(matrix, target, rcond=None)
    if rank != matrix.shape[1] or singular[0] / singular[-1] > 1e8:
        raise ValueError('Точки недостаточно различаются для устойчивого расчёта. Добавьте промежуточные положения.')
    return coef


def predict_profile(profile, high, low):
    """Return a candidate and branch margin; validation belongs to the caller."""
    h, low = wrap(high), wrap(low)
    if 'low_linear_deg_per_m' in profile:
        a, b = profile['low_linear_deg_per_m']
        coarse_mm = 1000.0 * (low - a) / b
    else:
        a, b, s, c = profile['low_harmonic_deg_per_m']
        radians = math.radians(h)
        coarse_mm = 1000.0 * (low - a - s * math.sin(radians) - c * math.cos(radians)) / b
    a, b = profile['high_forward_deg_per_m']
    predicted_u = a + b * coarse_mm / 1000.0
    turns = round((predicted_u - h) / 360.0)
    u = h + 360.0 * turns
    margin = 180.0 - abs(predicted_u - u)
    x = -u / 360.0
    if 'fine_mm' in profile:
        z = (x - profile['x_center_turns']) / profile['x_scale_turns']
        distance = 0.0
        for coefficient in reversed(profile['fine_mm']):
            distance = distance * z + coefficient
    else:
        c0, c1, c2, c3 = profile['cubic_mm']
        distance = ((c3 * x + c2) * x + c1) * x + c0
    return distance, margin, x, turns


def validate_model(model, demo):
    """Validate disk data independently from ordinary COM/DDS settings."""
    try:
        if model['schema'] != 1 or model['method'] not in (METHOD, LEGACY_METHOD) or model['demo'] is not bool(demo):
            raise ValueError('Неизвестный метод или другой режим калибровки (ДЕМО/приборы).')
        if not isinstance(model['point_count'], int) or model['point_count'] < MIN_POINTS:
            raise ValueError('Недостаточно точек в сохранённой калибровке.')
        for key in ('points_sha256', 'id'):
            if not isinstance(model[key], str) or len(model[key]) != 64 or any(c not in '0123456789abcdef' for c in model[key]):
                raise ValueError('Некорректный идентификатор калибровки.')
        for key in ('distance_range_mm',):
            values = model[key]
            if len(values) != 2 or not all(finite(v) for v in values) or not 0 <= values[0] < values[1]:
                raise ValueError('Некорректная область калибровки.')
        for channel in ('analog', 'digital'):
            p = model['profiles'][channel]
            modern = model['method'] == METHOD
            coarse = ('low_linear_deg_per_m',2) if 'low_linear_deg_per_m' in p else ('low_harmonic_deg_per_m',4)
            coefficients = (coarse,('fine_mm',5)) if modern else (('low_harmonic_deg_per_m',4),('cubic_mm',4))
            for key, length in (('high_forward_deg_per_m', 2), ('x_range_turns', 2), *coefficients):
                values = p[key]
                if not isinstance(values, list) or len(values) != length or not all(finite(v) for v in values):
                    raise ValueError('Некорректные коэффициенты калибровки.')
            low_key = coarse[0] if modern else 'low_harmonic_deg_per_m'
            if p['high_forward_deg_per_m'][1] >= 0 or p[low_key][1] <= 0:
                raise ValueError('Неподдерживаемое направление изменения фаз.')
            xmin, xmax = p['x_range_turns']
            if xmax - xmin < 1:
                raise ValueError('Нужны точки хотя бы на одном полном обороте ВЧ-фазы.')
            if modern:
                if not finite(p['x_center_turns']) or not finite(p['x_scale_turns']) or p['x_scale_turns'] <= 0:
                    raise ValueError('Некорректный масштаб ВЧ-фазы.')
                xmin, xmax = [(x-p['x_center_turns'])/p['x_scale_turns'] for x in (xmin,xmax)]
            derivative = np.polynomial.Polynomial(p['fine_mm'] if modern else p['cubic_mm']).deriv()
            extrema = [xmin, xmax] + [float(r.real) for r in derivative.deriv().roots()
                                     if abs(r.imag) < 1e-10 and xmin < r.real < xmax]
            if any(derivative(x) <= 0 for x in extrema):
                raise ValueError('Расчётная дальность немонотонна. Нужны дополнительные стабильные точки.')
            if not finite(p['min_branch_margin_deg']) or not 0 < p['min_branch_margin_deg'] < 180:
                raise ValueError('Некорректный запас выбора периода.')
            if not all(finite(p[k]) and p[k] >= 0 for k in ('fit_rms_mm', 'fit_max_abs_mm')):
                raise ValueError('Некорректные показатели подгонки.')
        canonical = deepcopy(model)
        identity = canonical.pop('id')
        encoded = json.dumps(canonical, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if hashlib.sha256(encoded.encode('utf-8')).hexdigest() != identity:
            raise ValueError('Контрольная сумма калибровки не совпадает.')
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError('Повреждён файл коэффициентов калибровки.') from error
    return model


def fit_calibration(points, *, demo=False, source='', dds_settings=None, confirmed_dds=None, method=METHOD):
    if method not in (METHOD, LEGACY_METHOD):
        raise ValueError('Неизвестный метод калибровки.')
    data = normalized_points(points)
    if len(data) < MIN_POINTS:
        raise ValueError(f'Для расчёта нужно не менее {MIN_POINTS} разных точек; сейчас {len(data)}.')
    d = np.array([p['distance_mm'] for p in data])
    profiles = {}
    for channel in ('analog', 'digital'):
        high, low = [np.array([wrap(p['phases'][f'{channel}_{band}_deg']) for p in data]) for band in ('high', 'low')]
        # Training positions and the RF prior resolve gaps larger than half a cycle.
        slope = -.180
        if confirmed_dds and method == METHOD:
            high_hz = (confirmed_dds[1]['ftw']+confirmed_dds[3]['ftw'])/2 * 500_000_000/2**32
            slope = -720 * high_hz / 299_792_458_000
        delta = (np.diff(high) + 180) % 360 - 180
        delta += 360 * np.rint((slope * np.diff(d) - delta) / 360)
        u = np.r_[high[0], high[0] + np.cumsum(delta)]
        if np.any(np.diff(u) >= 0) or np.any(np.abs(np.diff(low)) >= 180):
            raise ValueError('Фазы нарушают ожидаемый порядок дальности. Проверьте точки и порядок каналов.')
        x = -u / 360
        base = np.c_[np.ones(len(d)), d / 1000]
        modern = method == METHOD
        coarse = base if modern else np.c_[base, np.sin(np.deg2rad(high)), np.cos(np.deg2rad(high))]
        center, scale = (float(x[0])+float(x[-1]))/2, float(x[-1]-x[0])/2
        if scale <= 0:
            raise ValueError('Недостаточный диапазон ВЧ-фазы.')
        z = (x-center)/scale if modern else x
        fine = np.polynomial.polynomial.polyvander(z, 4 if modern else 3)
        high_coef, low_coef, fine_coef = solve(base, u), solve(coarse, low), solve(fine, d)
        if high_coef[1] >= 0 or low_coef[1] <= 0 or x[-1] - x[0] < 1:
            raise ValueError('Недостаточный диапазон точек: нужен полный оборот ВЧ и рост НЧ в среднем.')
        errors = fine @ fine_coef - d
        profile = dict(high_forward_deg_per_m=high_coef.tolist(), x_range_turns=[float(x[0]), float(x[-1])],
                       min_branch_margin_deg=90.0, fit_rms_mm=float(np.sqrt(np.mean(errors**2))),
                       fit_max_abs_mm=float(np.max(np.abs(errors))))
        if modern:
            profile.update(low_linear_deg_per_m=low_coef.tolist(),fine_mm=fine_coef.tolist(),
                           x_center_turns=center,x_scale_turns=scale)
        else:
            profile.update(low_harmonic_deg_per_m=low_coef.tolist(),cubic_mm=fine_coef.tolist())
        def branches_ok():
            for i in range(len(d)):
                _, margin, _, turns = predict_profile(profile, float(high[i]), float(low[i]))
                if margin < profile['min_branch_margin_deg'] or abs(high[i] + 360 * turns - u[i]) > 1e-6:
                    return False
            return True
        if modern and not branches_ok():
            # Older data can have periodic LF errors. Correct only branch selection.
            corrected = solve(np.c_[base,np.sin(np.deg2rad(high)),np.cos(np.deg2rad(high))], low)
            if corrected[1] <= 0:
                raise ValueError('Неподдерживаемое направление НЧ-фазы.')
            del profile['low_linear_deg_per_m']
            profile['low_harmonic_deg_per_m'] = corrected.tolist()
        if not branches_ok():
            raise ValueError('Точки не обеспечивают надёжный выбор периода. Добавьте стабильные измерения.')
        profiles[channel] = profile
    model = dict(schema=1, method=method, created_utc=datetime.now(timezone.utc).isoformat(), demo=bool(demo),
                 point_count=len(data), points_sha256=points_digest(data), source=str(source),
                 dds_settings_not_readback=deepcopy(dds_settings), distance_range_mm=[float(d[0]), float(d[-1])],
                 profiles=profiles)
    if confirmed_dds is not None:
        # Only a bank recorded with the source series can bind a new calibration.
        from .model import dds_channels, dds_rows
        if dds_channels(dds_rows(confirmed_dds)) != confirmed_dds:
            raise ValueError('Некорректный банк DDS калибровки.')
        model['dds_channels'] = deepcopy(confirmed_dds)
    encoded = json.dumps(model, sort_keys=True, separators=(',', ':'), allow_nan=False)
    model['id'] = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
    return validate_model(model, demo)


def estimate_distance(model, row, channel='analog'):
    def invalid(reason):
        return dict(valid=False, distance_mm=None, reason=reason)
    if model is None:
        return invalid('not_calibrated')
    if row.get('protocol_version') == 3:
        if not row.get('dds_channels') or row.get('configuring'):
            return invalid('dds_unknown')
        if not model.get('dds_channels'):
            return invalid('dds_unbound')
        if row['dds_channels'] != model['dds_channels']:
            return invalid('dds_mismatch')
    if not row.get('valid') or not row.get('fresh') or row.get('beam_lost'):
        return invalid('invalid_signal')
    keys = [f'{channel}_{band}_deg' for band in ('high', 'low')]
    if not all(finite(row.get(key)) and row.get(key.replace('_deg', '_valid'), row['valid']) for key in keys):
        return invalid('invalid_signal')
    profile = model['profiles'][channel]
    try:
        distance, margin, x, turns = predict_profile(profile, *(row[key] for key in keys))
    except (OverflowError, ValueError, ZeroDivisionError):
        return invalid('invalid_signal')
    if not math.isfinite(distance):
        return invalid('invalid_signal')
    if margin < profile['min_branch_margin_deg']:
        return invalid('ambiguous_branch')
    if not profile['x_range_turns'][0] - 1e-12 <= x <= profile['x_range_turns'][1] + 1e-12:
        return invalid('outside_calibration')
    return dict(valid=True, distance_mm=distance, reason='ok', branch_margin_deg=margin, turns=turns)


class DistanceStore:
    def __init__(self, settings_path, demo=False):
        path = Path(settings_path)
        self.path = path.with_name(path.stem + '-distance-calibration.json')
        self.demo = demo

    def load(self):
        if not self.path.exists():
            return None, ''
        try:
            model = json.loads(self.path.read_text(encoding='utf-8'))
            return validate_model(model, self.demo), ''
        except (OSError, ValueError, TypeError) as error:
            return None, 'Калибровка не загружена: ' + str(error) + ' Исходный файл сохранён без изменений.'

    def save(self, model):
        validate_model(model, self.demo)
        encoded = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

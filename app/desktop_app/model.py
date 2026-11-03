"""Settings, DDS validation and timestamp pairing; no GUI or device ownership."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DDS_CLOCK_HZ = 500_000_000
PROFILE_NAME = "Стенд 1642 мм · 03.11.2026"
PROFILE_CHANNELS = [dict(ftw=f, phase_word=0, amplitude=a) for f, a in
                    ((12845056, 200), (635888254, 1000), (12879416, 1000), (635830272, 450))]
LEGACY_DDS = [dict(frequency_mhz=f * 500 / 2**32, phase_deg=0.0, amplitude=a) for f, a in
              ((12884902, 200), (644348174, 500), (12987981, 150), (644245095, 300))]


def dds_rows(channels):
    return [dict(frequency_mhz=c['ftw'] * 500 / 2**32,
                 phase_deg=c['phase_word'] * 360 / 16384, amplitude=c['amplitude']) for c in channels]


DEFAULTS = {
    "schema": 2,
    "port": "", "baud": 115200, "bits": 8, "parity": "N", "stop_bits": 1,
    "fpga_interval_ms": 10, "fpga_timeout_ms": 100,
    "vector_enabled": False, "vector_address": "",
    "vector_usb_transport": "usb:0B05:1D70",
    "vector_interval_s": 1.0, "vector_timeout_s": 3.0,
    "history_s": 60, "x_axis": "time",
    "calibration_file": "",
    "selected": ["analog_high_deg", "analog_low_deg", "digital_high_deg", "digital_low_deg"],
    "dds": dds_rows(PROFILE_CHANNELS),
}

# key, Russian label, unit, selector group
FIELDS = [
    ("analog_high_deg", "Фаза АЦП · ВЧ", "°", "Фазы"),
    ("analog_low_deg", "Фаза АЦП · НЧ", "°", "Фазы"),
    ("digital_high_deg", "Цифровая фаза · ВЧ", "°", "Фазы"),
    ("digital_low_deg", "Цифровая фаза · НЧ", "°", "Фазы"),
    ("digital_high_rise_deg", "ВЧ · нарастающий фронт", "°", "Фазы фронтов"),
    ("digital_high_fall_deg", "ВЧ · спадающий фронт", "°", "Фазы фронтов"),
    ("digital_low_rise_deg", "НЧ · нарастающий фронт", "°", "Фазы фронтов"),
    ("digital_low_fall_deg", "НЧ · спадающий фронт", "°", "Фазы фронтов"),
] + [(f"ch{i}_peak_v", f"Амплитуда сигнала {i}", "В", "Амплитуды") for i in range(1, 5)] + [
    (f"detector{i}_v", f"Детектор {i}", "В", "Детекторы") for i in range(1, 5)
] + [
    ("digital_high_frequency_hz", "Измеренная ПЧ · ВЧ", "Гц", "Частоты"),
    ("digital_low_frequency_hz", "Измеренная ПЧ · НЧ", "Гц", "Частоты"),
    ("expected_high_frequency_hz", "Заданная ПЧ · ВЧ", "Гц", "Частоты"),
    ("expected_low_frequency_hz", "Заданная ПЧ · НЧ", "Гц", "Частоты"),
    ("vector_mm", "Расстояние Vector60", "мм", "Рулетка"),
    ("phase_distance_mm", "Расстояние по фазам АЦП (ПК)", "мм", "Расчётная дальность"),
] + [(f"adc{i}_v", f"АЦП {i} · отсчёт", "В", "Отсчёты АЦП") for i in range(1, 9)]
FIELD_MAP = {key: (label, unit, group) for key, label, unit, group in FIELDS}


def number(value, label, minimum, maximum):
    try:
        result = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: введите число.") from None
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label}: допустимо от {minimum:g} до {maximum:g}.")
    return result


def validate_dds(rows):
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("DDS: необходимо заполнить четыре канала.")
    result = []
    for i, row in enumerate(rows):
        f = number(row["frequency_mhz"], f"CH{i}, частота (МГц)", 0, 250)
        phase = number(row["phase_deg"], f"CH{i}, фаза (°)", 0, 360)
        amp = number(row["amplitude"], f"CH{i}, амплитуда", 0, 1023)
        if not 1 <= round(f / 500 * 2**32) <= 0x7fffffff or phase >= 360:
            raise ValueError(f"CH{i}: частота должна быть больше нуля и меньше 250 МГц, фаза — меньше 360°.")
        if not amp.is_integer():
            raise ValueError(f"CH{i}: код амплитуды должен быть целым.")
        result.append(dict(frequency_mhz=f, phase_deg=phase, amplitude=int(amp)))
    return result


def dds_channels(rows, check_if=True):
    """Quantize once; validate IF limits using the actual words sent on the wire."""
    rows = validate_dds(rows)
    channels = [dict(ftw=round(r['frequency_mhz'] / 500 * 2**32),
                     phase_word=round(r['phase_deg'] / 360 * 16384) & 0x3fff,
                     amplitude=r['amplitude']) for r in rows]
    if check_if:
        for a, b, label in ((2, 0, 'НЧ: CH2 − CH0'), (1, 3, 'ВЧ: CH1 − CH3')):
            if not 8590 <= channels[a]['ftw'] - channels[b]['ftw'] <= 171799:
                raise ValueError(f'ПЧ {label} должна быть положительной, от 1 до 20 кГц (FTW 8590…171799).')
    return channels


def is_legacy_default(rows):
    try:
        return dds_channels(rows, check_if=False) == dds_channels(LEGACY_DDS, check_if=False)
    except (ValueError, KeyError, TypeError):
        return False


def dds_intermediate_frequencies(rows):
    """Preview IF from quantized frequencies; independent of ASF/POW edits."""
    words = []
    for i, row in enumerate(rows):
        value = number(row['frequency_mhz'], f'CH{i}, частота (МГц)', 0, 250)
        word = round(value / 500 * 2**32)
        if not 1 <= word <= 0x7fffffff:
            raise ValueError('Частота должна быть больше нуля и меньше 250 МГц.')
        words.append(word)
    if len(words) != 4:
        raise ValueError('Нужны четыре частоты DDS.')
    return dict(low=(words[2]-words[0])*DDS_CLOCK_HZ/2**32,
                high=(words[1]-words[3])*DDS_CLOCK_HZ/2**32)


def validate_settings(data):
    s = deepcopy(DEFAULTS)
    s.update({k: v for k, v in data.items() if k in s})
    if s["schema"] not in (1, 2):
        raise ValueError("Неизвестная версия файла настроек.")
    if s['schema'] == 1 and is_legacy_default(s['dds']):
        s['dds'] = deepcopy(DEFAULTS['dds'])
    s['schema'] = 2
    if not isinstance(s["port"], str) or len(s["port"]) > 128:
        raise ValueError("Укажите COM-порт.")
    s["port"] = s["port"].strip()
    for key, label, lo, hi in [("baud", "Скорость порта", 1200, 3000000),
                                ("fpga_interval_ms", "Период FPGA (мс)", 1, 60000),
                                ("fpga_timeout_ms", "Тайм-аут FPGA (мс)", 30, 10000),
                                ("history_s", "История графика (с)", 10, 3600)]:
        v = number(s[key], label, lo, hi)
        if not v.is_integer():
            raise ValueError(f"{label}: введите целое число.")
        s[key] = int(v)
    if s["bits"] not in (5, 6, 7, 8) or s["parity"] not in ("N", "E", "O", "M", "S") or s["stop_bits"] not in (1, 1.5, 2):
        raise ValueError("Недопустимый формат COM-порта.")
    for key, label, lo, hi in [("vector_interval_s", "Период рулетки (с)", .1, 3600),
                                ("vector_timeout_s", "Тайм-аут рулетки (с)", .2, 60)]:
        s[key] = number(s[key], label, lo, hi)
    import re
    if not isinstance(s["vector_address"], str) or (s["vector_address"] and not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", s["vector_address"])):
        raise ValueError("Адрес Vector60: используйте формат AA:BB:CC:DD:EE:FF.")
    if not isinstance(s['vector_usb_transport'], str) or not re.fullmatch(r'usb:[0-9a-fA-F]{4}:[0-9a-fA-F]{4}', s['vector_usb_transport']):
        raise ValueError('USB-адаптер: используйте формат usb:VID:PID, по четыре шестнадцатеричные цифры.')
    if not isinstance(s["vector_enabled"], bool) or s["x_axis"] not in ("time", "distance"):
        raise ValueError("Недопустимые настройки графика.")
    if not isinstance(s["selected"], list):
        raise ValueError("Некорректный список кривых.")
    s["selected"] = list(dict.fromkeys(k for k in s["selected"] if isinstance(k, str) and k in FIELD_MAP))
    s["dds"] = validate_dds(s["dds"])
    if not isinstance(s['calibration_file'], str):
        raise ValueError('Некорректный путь серии калибровки.')
    return s


class SettingsStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "LaserRangefinder" / "settings.json"

    def load(self):
        if not self.path.exists():
            return deepcopy(DEFAULTS), ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Ожидался объект JSON.")
            migrated = data.get('schema') == 1 and is_legacy_default(data.get('dds'))
            return validate_settings(data), ("Прежние стартовые DDS заменены выбранным стендовым профилем. Для применения нажмите «Отправить в FPGA»." if migrated else "")
        except (OSError, ValueError, TypeError, KeyError) as error:
            backup = self.path.with_name("settings-invalid-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
            try:
                shutil.copyfile(self.path, backup)
                detail = f"Исходный файл сохранён: {backup.name}."
            except OSError:
                detail = "Не удалось сохранить копию исходного файла."
            return deepcopy(DEFAULTS), f"Загружены настройки по умолчанию: {error} {detail}"

    def save(self, data):
        checked = validate_settings(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                old = json.loads(self.path.read_text(encoding='utf-8'))
                if old.get('schema') == 1:
                    backup = self.path.with_name(self.path.stem + '-before-v3-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
                    shutil.copyfile(self.path, backup)
            except (ValueError, AttributeError):
                pass
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as f:
                name = f.name
                json.dump(checked, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if name and Path(name).exists():
                Path(name).unlink()


class History:
    """Receipt-time pairing, never interpolation or reuse of a stale distance."""
    def __init__(self, capacity=20000):
        self.fpga = deque(maxlen=capacity)
        self.vector = deque(maxlen=capacity)
        self.paired = deque(maxlen=capacity)
        self.last_fpga = None

    def add_fpga(self, stamp, row):
        values = dict(row)
        # Invalid phase need not invalidate a genuine low-amplitude ADC result.
        fresh = values.get("fresh", True)
        for key in FIELD_MAP:
            valid = fresh
            if key.endswith("_deg"):
                valid &= values.get(key.replace("_deg", "_valid"), values.get("valid", False))
            elif key == 'phase_distance_mm':
                valid &= values.get('phase_distance_valid', False)
            elif key.startswith("ch"):
                valid &= bool(values.get("adc_ok", 0) & (1 << (int(key[2]) - 1)))
            elif key.startswith("detector"):
                valid &= bool(values.get("adc_ok", 0) & (1 << (int(key[8]) + 3)))
            elif key.startswith("adc"):
                valid &= bool(values.get("adc_ok", 0) & (1 << (int(key[3]) - 1)))
            elif key.startswith("digital_"):
                valid &= values.get(key.replace("_frequency_hz", "_valid"), values.get("valid", False))
            if not valid:
                values[key] = None
        self.fpga.append((stamp, values))
        self.last_fpga = (stamp, values)

    def add_vector(self, stamp, distance_mm, max_age=.1):
        self.vector.append((stamp, {"vector_mm": distance_mm}))
        values = {"vector_mm": distance_mm}
        if distance_mm is not None and self.last_fpga:
            for t, row in reversed(self.fpga):
                if t <= stamp:
                    if stamp - t <= max_age and row.get("valid"):
                        values.update(row)
                    break
        self.paired.append((stamp, distance_mm, values))

    def series(self, key, axis, window_s):
        collections = (self.fpga, self.vector, self.paired)
        latest = max((q[-1][0] for q in collections if q), default=0)
        left = latest - window_s
        x, y = [], []
        if axis == "distance":
            source = ((t, d, row) for t, d, row in self.paired if t >= left)
        else:
            source = ((t, t, row) for t, row in (self.vector if key == "vector_mm" else self.fpga) if t >= left)
        for _, xx, row in source:
            value = row.get(key)
            x.append(float("nan") if xx is None else xx)
            y.append(float("nan") if value is None else value)
        return x, y

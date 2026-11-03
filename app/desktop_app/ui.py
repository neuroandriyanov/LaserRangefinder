"""Russian Tk desktop UI with bounded history and unit-separated charts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .model import (DEFAULTS, FIELDS, FIELD_MAP, History, SettingsStore, PROFILE_NAME,
                    PROFILE_CHANNELS, dds_channels, dds_intermediate_frequencies, validate_dds, validate_settings)
from .workers import DeviceWorker
from .calibration_view import CalibrationTab
from .distance import DistanceStore, REASONS, estimate_distance

BG = "#f3eee6"
PANEL = "#fffcf7"
INK = "#293d36"
MUTED = "#778078"
ACCENT = "#326b59"
AMBER = "#a4682b"
RED = "#ab4a3e"
COLORS = ["#327765", "#c2813f", "#527da2", "#ae5c68", "#7d6aa2", "#55a095", "#a78b37", "#7e6260"]


class App:
    def __init__(self, root, store=None, demo=False, log_base=None):
        self.root, self.store, self.demo, self.log_base = root, store or SettingsStore(), demo, log_base
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)
        self.settings, warning = self.store.load()
        self.distance_store = DistanceStore(self.store.path, demo=demo)
        self.distance_model, self.distance_warning = self.distance_store.load()
        self.distance_result = estimate_distance(self.distance_model, {})
        self.events = queue.Queue(maxsize=10000)
        self.workers = {"fpga": None, "vector": None}
        self.active_config = None
        self.dds_pending = False
        self.history = History()
        self.origin = time.monotonic()
        self.last_fpga = self.last_vector = None
        self.last_fpga_at = self.last_vector_at = None
        self.fpga_current = self.vector_current = False
        self.last_packets = 0
        self.rate_times = []
        self.closing = False
        self.plot_dirty = True
        self.last_plot = 0
        self.plot_signature = None
        self.saved_serialized = None
        self.help_text = tk.StringVar(value="Готово. Выберите прибор и запустите опрос.")
        self.connection_text = tk.StringVar(value="Приборы отключены")
        self.state_text = tk.StringVar(value="ДЕМОНСТРАЦИЯ" if demo else "Ожидание")
        self.vector_enabled = tk.BooleanVar(value=self.settings["vector_enabled"])
        self.axis = tk.StringVar(value="Расстояние, мм" if self.settings["x_axis"] == "distance" and self.vector_enabled.get() else "Время, с")
        self.selected = {k: tk.BooleanVar(value=k in self.settings["selected"]) for k, *_ in FIELDS}
        self.card_vars = {}
        self.dds_vars = []
        self._style()
        self._build()
        self._center()
        self._axis_options()
        root.protocol("WM_DELETE_WINDOW", self.close)
        if warning:
            self.log(warning)
            self.help_text.set(warning)
        if self.distance_warning:
            self.log(self.distance_warning)
        elif self.distance_model:
            self.log('Коэффициенты расстояния загружены: '+str(self.distance_store.path))
        self.root.after(40, self.tick)
        if demo:
            self.root.after(300, self.start_demo)

    def _style(self):
        self.root.title("Лазерный дальномер" + (" — ДЕМО" if self.demo else ""))
        self.root.configure(bg=BG)
        self.root.minsize(round(1040 * self.scale), round(680 * self.scale))
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Panel.TLabel", background=PANEL)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Small.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Badge.TLabel", background="#e4e9de", foreground=ACCENT, padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 8), background="#e8e1d7", borderwidth=0)
        style.map("TButton", background=[("active", "#dcd3c5")], foreground=[("disabled", "#a6aaa4")])
        style.configure("Accent.TButton", foreground="white", background=ACCENT)
        style.map("Accent.TButton", background=[("active", "#245340"), ("disabled", "#d4dbd1")])
        style.configure("TCheckbutton", background=PANEL, padding=(3, 5))
        style.configure("TNotebook", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(22, 10))
        style.map("TNotebook.Tab", background=[("selected", PANEL)])
        style.configure("TEntry", fieldbackground="white", padding=7)
        style.configure("TCombobox", fieldbackground="white", padding=5)
        table_font = tkfont.Font(root=self.root, font=style.lookup("Treeview", "font"))
        row_height = max(round(30 * self.scale), table_font.metrics("linespace") + round(12 * self.scale))
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=row_height, borderwidth=0)
        style.configure("Treeview.Heading", background="#e8e1d7", padding=7)

    def hint(self, widget, text):
        widget.bind("<Enter>", lambda event: self.help_text.set(text), add="+")
        widget.bind("<Leave>", lambda event: self.help_text.set("Готово." if not self.closing else "Завершение опроса…"), add="+")
        widget.bind("<FocusIn>", lambda event: self.help_text.set(text), add="+")
        return widget

    def _build(self):
        menu = tk.Menu(self.root)
        file = tk.Menu(menu, tearoff=False)
        file.add_command(label="Сохранить график…", command=self.export_chart)
        file.add_command(label="Очистить график", command=self.clear_chart)
        file.add_separator()
        file.add_command(label="Выход", command=self.close)
        menu.add_cascade(label="Файл", menu=file)
        settings = tk.Menu(menu, tearoff=False)
        settings.add_command(label="COM-порт и опрос…", command=self.preferences)
        settings.add_command(label="Калибровка дальномера…", command=lambda: self.notebook.select(self.calibration.parent))
        settings.add_command(label="Параметры DDS и смещение фазы…", command=lambda: self.notebook.select(self.dds_tab))
        menu.add_cascade(label="Настройки", menu=settings)
        self.root.configure(menu=menu)
        outer = ttk.Frame(self.root, padding=(22, 18, 22, 0))
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 16))
        title = ttk.Frame(header)
        title.pack(side="left")
        ttk.Label(title, text="Лазерный дальномер", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Измерения FPGA и контрольное расстояние Vector60", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))
        self.badge = ttk.Label(header, textvariable=self.state_text, style="Badge.TLabel")
        self.badge.pack(side="right")
        self.hint(self.badge, "Достоверность текущих измерений и диагностические замечания. ДЕМО не обращается к приборам.")
        if self.demo:
            ttk.Label(outer, text="ДЕМОНСТРАЦИОННЫЙ РЕЖИМ · синтетические данные, приборы не подключаются", foreground=AMBER).pack(anchor="w", pady=(0, 10))
        control = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        control.pack(fill="x", pady=(0, 14))
        self.fpga_button = self.hint(ttk.Button(control, text="Запустить FPGA", style="Accent.TButton", command=lambda: self.toggle("fpga")), "Начать или остановить опрос FPGA. Одновременно ожидается только один ответ; каждый пакет проверяется по CRC.")
        self.fpga_button.pack(side="left")
        self.port_text = tk.StringVar()
        self._port_caption()
        self.hint(ttk.Label(control, textvariable=self.port_text, style="Panel.TLabel"), "Формат соединения и плановый период. Реальная частота зависит от времени ответа FPGA.").pack(side="left", padx=12)
        self.settings_button = self.hint(ttk.Button(control, text="Настройки…", command=self.preferences), "Выбор COM-порта, формата обмена, периодов и тайм-аутов. Настройки сохраняются.")
        self.settings_button.pack(side="left")
        self.vector_button = self.hint(ttk.Button(control, text="Запустить рулетку", command=lambda: self.toggle("vector")), "Подключить Vector60 и начать последовательные запросы. Кнопка повторного нажатия останавливает опрос и освобождает адаптер.")
        self.vector_button.pack(side="right")
        self.vector_check = self.hint(ttk.Checkbutton(control, text="Подключить Vector60", variable=self.vector_enabled, command=self.vector_changed), "Разрешает опрос рулетки и график по расстоянию. Сам опрос начинается кнопкой «Запустить рулетку».")
        self.vector_check.pack(side="right", padx=15)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        measure = ttk.Frame(notebook, padding=12, style="Panel.TFrame")
        values = ttk.Frame(notebook, padding=16, style="Panel.TFrame")
        calibration = ttk.Frame(notebook, padding=16, style="Panel.TFrame")
        dds = ttk.Frame(notebook, padding=22, style="Panel.TFrame")
        notebook.add(measure, text="Измерения")
        notebook.add(values, text="Все значения")
        notebook.add(calibration, text="Калибровка дальномера")
        notebook.add(dds, text="Параметры DDS")
        self.dds_tab = dds
        self.notebook = notebook
        self.hint(notebook, "Измерения: график. Все значения: последний ответ. Калибровка: запись точек. DDS: параметры четырёх каналов.")
        cards = ttk.Frame(measure, style="Panel.TFrame")
        cards.pack(fill="x", pady=(0, 14))
        for col, (key, title, unit) in enumerate([
            ("analog_high_deg", "Фаза АЦП · ВЧ", "°"), ("analog_low_deg", "Фаза АЦП · НЧ", "°"),
            ("digital_high_deg", "Цифровая · ВЧ", "°"), ("digital_low_deg", "Цифровая · НЧ", "°"),
            ("vector_mm", "Расстояние Vector60", "мм"),
            ("phase_distance_mm", "По фазам АЦП · ПК", "мм")]):
            cards.columnconfigure(col, weight=1, uniform="card")
            frame = tk.Frame(cards, bg="#eee9df", padx=13, pady=12)
            frame.grid(row=0, column=col, sticky="nsew", padx=(0, 7 if col < 5 else 0))
            label = tk.Label(frame, text=title, width=1, bg="#eee9df", fg=MUTED, anchor="w", font=("Segoe UI", 9))
            label.pack(fill="x")
            var = tk.StringVar(value="—")
            self.card_vars[key] = var
            number_label = tk.Label(frame, textvariable=var, width=1, bg="#eee9df", fg=INK, font=("Segoe UI", 21, "bold"), anchor="w")
            number_label.pack(fill="x", pady=(6, 0))
            self.hint(number_label, f"{title}, {unit}. Прочерк означает отсутствие актуального достоверного значения.")
            if key == 'phase_distance_mm':
                self.distance_status = tk.StringVar(value=REASONS['not_calibrated'] if not self.distance_model else 'Ожидание FPGA')
                status = tk.Label(frame,textvariable=self.distance_status,width=1,height=1,bg='#eee9df',fg=MUTED,
                                  anchor='w',font=('Segoe UI',8))
                status.pack(fill='x',pady=(3,0))
                self.hint(status,'Расчёт на ПК по двум аналоговым фазам. НЧ выбирает оборот, кубический МНК ВЧ уточняет мм. Требуется сохранённая калибровка и свежий сигнал.')
        chart_top = ttk.Frame(measure, style="Panel.TFrame")
        chart_top.pack(fill="x", pady=(0, 6))
        ttk.Label(chart_top, text="График измерений", style="Panel.TLabel", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.hint(ttk.Button(chart_top, text="Кривые ▾", command=self.toggle_selector), "Показать или скрыть список параметров с чекбоксами.").pack(side="right")
        self.hint(ttk.Button(chart_top, text="Очистить", command=self.clear_chart), "Очистить только график. Исходные журналы сеансов сохраняются.").pack(side="right", padx=6)
        self.axis_combo = self.hint(ttk.Combobox(chart_top, textvariable=self.axis, state="readonly", width=19), "Ось X: время получения или расстояние Vector60 в мм. По расстоянию строятся только свежие пары ответов, без интерполяции.")
        self.axis_combo.pack(side="right", padx=8)
        self.axis_combo.bind("<<ComboboxSelected>>", lambda event: self.chart_changed())
        ttk.Label(chart_top, text="Ось X:", style="Panel.TLabel").pack(side="right")
        plot_area = ttk.Frame(measure, style="Panel.TFrame")
        plot_area.pack(fill="both", expand=True)
        plot_area.rowconfigure(0, weight=1)
        plot_area.columnconfigure(0, weight=1)
        figure_frame = ttk.Frame(plot_area, style="Panel.TFrame")
        figure_frame.grid(row=0, column=0, sticky="nsew")
        # TkAgg applies the monitor's device pixel ratio itself.
        self.figure = Figure(figsize=(8, 4.5), dpi=100, facecolor=PANEL, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=figure_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.hint(self.canvas.get_tk_widget(), "Масштаб меняется автоматически. Разные единицы показаны на отдельных шкалах. Пропуски и недостоверные отсчёты разрывают линии.")
        self.selector = ttk.Frame(plot_area, width=round(235 * self.scale), padding=(14, 4, 0, 0), style="Panel.TFrame")
        self.selector.grid(row=0, column=1, sticky="ns")
        self.selector_visible = True
        ttk.Label(self.selector, text="Показать на графике", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        scroll = tk.Canvas(self.selector, bg=PANEL, highlightthickness=0, width=round(222 * self.scale))
        bar = ttk.Scrollbar(self.selector, orient="vertical", command=scroll.yview)
        bar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        scroll.configure(yscrollcommand=bar.set)
        inner = ttk.Frame(scroll, style="Panel.TFrame")
        scroll.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
        self.vector_curve = None
        group = None
        for i, (key, label, unit, category) in enumerate(FIELDS):
            if category != group:
                ttk.Label(inner, text=category, style="Panel.TLabel", foreground=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(12, 3))
                group = category
            check = ttk.Checkbutton(inner, text=label, variable=self.selected[key], command=self.chart_changed)
            check.pack(anchor="w")
            self.hint(check, f"Показать: {label}, {unit}." + (" Напряжение детектора не является калиброванной амплитудой." if category == "Детекторы" else ""))
            check.bind("<MouseWheel>", lambda event: scroll.yview_scroll(-int(event.delta / 120), "units"))
            if key == "vector_mm":
                self.vector_curve = check
        self.chart_note = tk.StringVar(value="Автомасштаб • ожидаются данные")
        ttk.Label(measure, textvariable=self.chart_note, style="Panel.TLabel", foreground=MUTED, font=("Segoe UI", 9)).pack(side="bottom", anchor="w", pady=(5, 0), before=plot_area)
        self.values_caption = ttk.Label(values, text="Ожидание первого ответа", style="Panel.TLabel")
        self.values_caption.pack(anchor="w", pady=(0, 10))
        table_area = ttk.Frame(values, style="Panel.TFrame")
        table_area.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_area, columns=("name", "value", "unit"), show="headings", selectmode="browse")
        for name, text, width in (("name", "Параметр", 360), ("value", "Значение", 230), ("unit", "Единица", 90)):
            self.table.heading(name, text=text)
            self.table.column(name, width=round(width * self.scale), anchor="w")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_area, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.hint(self.table, "Снимок последнего полученного ответа. После остановки или тайм-аута значения в таблице исторические; статус показывает их актуальность.")
        for key, label, unit, _ in FIELDS:
            self.table.insert("", "end", iid=key, values=(label, "—", unit))
        extras = [(f"adc{i}_raw", f"АЦП {i} · исходный код", "код") for i in range(1, 9)] + [
            ("valid", "Достоверность FPGA", ""), ("beam_lost", "Потеря луча", ""),
            ("sequence", "Счётчик аналоговых измерений", ""), ("sample_index", "Номер выборки", ""),
            ("digital_sequence", "Счётчик цифровых измерений", ""), ("digital_age_ms", "Возраст цифровой фазы", "мс"),
            ("adc_ok", "Готовность АЦП", "маска"), ("diagnostics", "Диагностика FPGA", "маска"),
            ("fpga_distance", "Расстояние FPGA", "мм"), ("fpga_speed", "Скорость FPGA", "м/с")]
        extras += [
            ('protocol_version', 'Версия протокола', ''),
            ('request_id', 'Идентификатор запроса', ''),
            ('generation', 'Поколение конфигурации DDS', ''),
            ('configuring', 'Обновление DDS / установление сигнала', ''),
            ('delta_high', 'ПЧ ВЧ · разность FTW CH1 − CH3', 'код'),
            ('delta_low', 'ПЧ НЧ · разность FTW CH2 − CH0', 'код'),
            ('digital_high_period_ticks', 'Период ВЧ · такты 125 МГц', 'такты'),
            ('digital_low_period_ticks', 'Период НЧ · такты 125 МГц', 'такты'),
            ('flags', 'Флаги аналогового тракта', 'биты'),
            ('digital_flags', 'Флаги цифрового тракта', 'биты'),
            ('channel_valid', 'Маска достоверности аналоговых каналов', 'биты'),
            ('min_amplitude_counts', 'Порог амплитуды', 'коды АЦП'),
            ('window_samples', 'Окно аналогового фазомера', 'отсчёты'),
            ('digital_periods_averaged', 'Окно цифрового фазомера', 'периоды'),
            ('fresh', 'Свежий ответ по счётчикам', ''),
            ('roundtrip_ms', 'Время запроса и ответа FPGA', 'мс'),
        ] + [(f'ch{i}_peak_counts', f'Амплитуда сигнала {i} · коды АЦП', 'код') for i in range(1,5)] + [
            (f'detector{i}_raw', f'Детектор {i} · код', 'код') for i in range(1,5)]
        for key, label, *_ in FIELDS:
            if key.endswith('_deg'):
                extras += [(key.replace('_deg', '_raw_deg'), label + ' · исходная', '°'),
                           (key.replace('_deg', '_valid'), label + ' · достоверна', '')]
        for key, label, unit in extras:
            self.table.insert("", "end", iid=key, values=(label, "Не реализовано" if key.startswith("fpga_") else "—", unit))
        self._build_dds(dds)
        self.calibration = CalibrationTab(calibration, self)
        self.log_text = tk.Text(outer, height=3, wrap="word", bg=BG, fg=MUTED, relief="flat", font=("Segoe UI", 9), state="disabled")
        self.log_text.pack(side="bottom", fill="x", pady=(8, 4), before=notebook)
        self.hint(self.log_text, "События соединения, ошибки и пути к сохранённым данным. Полные записи не удаляются при очистке графика.")
        # Reserve space for two help lines and one connection line. Text changes
        # must not alter the notebook/chart geometry, including at high DPI.
        line_height = tkfont.Font(root=self.root, font=("Segoe UI", 9)).metrics("linespace")
        padding = round(8 * self.scale)
        footer = ttk.Frame(self.root, height=3 * line_height + 2 * padding)
        footer.pack(side="bottom", fill="x", before=outer)
        footer.pack_propagate(False)
        help_label = ttk.Label(footer, textvariable=self.help_text, style="Small.TLabel", anchor="nw")
        help_label.place(x=padding, y=padding, relwidth=1, width=-2 * padding, height=2 * line_height)
        footer.bind("<Configure>", lambda event: help_label.configure(wraplength=max(1, event.width - 2 * padding)))
        ttk.Label(footer, textvariable=self.connection_text, style="Small.TLabel", anchor="e").place(
            x=padding, rely=1, y=-padding, anchor="sw", relwidth=1, width=-2 * padding, height=line_height)

    def _build_dds(self, parent):
        canvas = tk.Canvas(parent, background=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(fill='both', expand=True)
        content = ttk.Frame(canvas, style='Panel.TFrame')
        item = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
        parent = content
        self.hint(ttk.Label(parent, text="Параметры DDS", style="Panel.TLabel", font=("Segoe UI", 18, "bold")),
                  'AD9959: 500 МГц. НЧ: CH0/CH2; ВЧ: CH1/CH3. Передача по UART v3.').pack(anchor="w",pady=(0,8))
        self.dds_profile_text = tk.StringVar()
        ttk.Label(parent, textvariable=self.dds_profile_text, style='Panel.TLabel').pack(anchor='w', pady=(0, 8))
        grid = ttk.Frame(parent, style="Panel.TFrame")
        grid.pack(anchor="w", fill="x")
        for col, title in enumerate(("Канал", "Частота, МГц", "Смещение фазы, °", "Амплитуда, код 0–1023")):
            ttk.Label(grid, text=title, style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=col, sticky="w", padx=10, pady=10)
        for i, row in enumerate(self.settings["dds"]):
            ttk.Label(grid, text=f"CH{i}", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=i + 1, column=0, padx=10, pady=6)
            variables = {}
            for col, key in enumerate(("frequency_mhz", "phase_deg", "amplitude"), 1):
                value = f"{row[key]:.12g}"
                var = tk.StringVar(value=value)
                variables[key] = var
                entry = ttk.Entry(grid, textvariable=var, width=25)
                entry.grid(row=i + 1, column=col, padx=10, pady=6, sticky="ew")
                help_text = {"frequency_mhz": "Частота больше 0 и меньше 250 МГц. ПЧ НЧ = CH2 − CH0, ВЧ = CH1 − CH3: 1–20 кГц.",
                             "phase_deg": "Смещение фазы DDS: 0 ≤ фаза < 360°. Шаг POW: 360/16384°. Измеренные фазы программно не корректируются.",
                             "amplitude": "Целый код амплитуды DDS от 0 до 1023. Это не напряжение и не мощность лазера."}[key]
                self.hint(entry, f"CH{i}. {help_text}")
                var.trace_add('write', lambda *_: self.dds_preview())
            self.dds_vars.append(variables)
        if_frame = ttk.Frame(parent, style='Panel.TFrame')
        if_frame.pack(anchor='w', pady=(8, 6))
        self.dds_if_vars = {band:tk.StringVar(value='—') for band in ('low','high')}
        self.dds_if_entries = {}
        for i,(band,label,pair) in enumerate((('low','ПЧ НЧ, Гц','CH2 − CH0'),('high','ПЧ ВЧ, Гц','CH1 − CH3'))):
            ttk.Label(if_frame,text=label,style='Panel.TLabel').grid(row=0,column=2*i,padx=(0,8))
            entry=ttk.Entry(if_frame,textvariable=self.dds_if_vars[band],state='readonly',width=19,justify='right')
            entry.grid(row=0,column=2*i+1,padx=(0,20))
            self.dds_if_entries[band]=entry
            self.hint(entry,f'Расчёт по введённым частотам после округления в FTW: {pair}. Поле только для чтения. Измеренная ПЧ находится во вкладке «Все значения».')
        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.pack(anchor="w", pady=(10, 6))
        self.dds_apply_button = self.hint(ttk.Button(actions, text="Отправить в FPGA", style="Accent.TButton", command=self.apply_dds), "Отправить весь банк четырёх каналов, выполнить одно синхронное обновление и сверить банк FPGA.")
        self.dds_apply_button.pack(side='left')
        self.hint(ttk.Button(actions, text="Сохранить параметры", command=self.save_dds), "Проверить и сохранить параметры DDS на ПК без отправки.").pack(side="left", padx=10)
        self.dds_read_button = self.hint(ttk.Button(actions, text='Прочитать FPGA', command=lambda: self.dds_command('read')), 'Прочитать активный банк FPGA без изменения полей ввода. Это не физическое SPI-чтение AD9959.')
        self.dds_read_button.pack(side='left')
        self.hint(ttk.Button(actions, text='Выбранный профиль', command=self.restore_dds_profile), 'Восстановить и сохранить на ПК профиль 03.11.2026 для мишени 1642 мм. Для применения нажмите «Отправить в FPGA».').pack(side='left', padx=10)
        self.dds_message = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.dds_message, style="Panel.TLabel", foreground=AMBER, wraplength=round(920*self.scale)).pack(anchor="w", pady=6)
        self.dds_active_text = tk.StringVar(value='DDS платы не прочитаны')
        ttk.Label(parent, textvariable=self.dds_active_text, style='Panel.TLabel', wraplength=round(920*self.scale)).pack(anchor='w', pady=(0, 8))
        self.dds_active_table = ttk.Treeview(parent, columns=('channel','frequency','phase','amplitude'), show='headings', height=4)
        for key, title in (('channel','Канал'),('frequency','Активная частота, Гц'),('phase','Активная фаза, °'),('amplitude','Амплитуда, код')):
            self.dds_active_table.heading(key,text=title)
            self.dds_active_table.column(key,width=round(210*self.scale),anchor='w')
        self.dds_active_table.pack(anchor='w',fill='x')
        for i in range(4):self.dds_active_table.insert('', 'end', iid=str(i), values=(f'CH{i}','—','—','—'))
        self.dds_preview()

    def _center(self):
        self.root.update_idletasks()
        width = min(round(1320 * self.scale), self.root.winfo_screenwidth() - round(60 * self.scale))
        height = min(round(870 * self.scale), self.root.winfo_screenheight() - round(100 * self.scale))
        self.root.geometry(f"{width}x{height}+{max(0, (self.root.winfo_screenwidth() - width) // 2)}+{max(0, (self.root.winfo_screenheight() - height) // 2)}")

    def _port_caption(self):
        s = self.settings
        self.port_text.set(f"{s['port']} · {s['baud']} · {s['bits']}{s['parity']}{s['stop_bits']:g}\nПериод {s['fpga_interval_ms']} мс")

    def _axis_options(self):
        enabled = self.vector_enabled.get()
        self.axis_combo.configure(values=["Время, с", "Расстояние, мм"] if enabled else ["Время, с"])
        if not enabled:
            self.axis.set("Время, с")
        self.vector_button.configure(state="normal" if enabled else "disabled")
        self.vector_curve.configure(state="normal" if enabled else "disabled")

    def persist(self, include_dds=False):
        self.settings["vector_enabled"] = self.vector_enabled.get()
        self.settings["selected"] = [k for k, v in self.selected.items() if v.get()]
        self.settings["x_axis"] = "distance" if self.axis.get() == "Расстояние, мм" else "time"
        if include_dds:
            rows = validate_dds([{k: v.get() for k, v in row.items()} for row in self.dds_vars])
            dds_channels(rows)
            self.settings["dds"] = rows
        serialized = json.dumps(self.settings, sort_keys=True)
        if serialized != self.saved_serialized:
            self.store.save(self.settings)
            self.saved_serialized = serialized

    def safe_persist(self):
        try:
            self.persist()
        except (OSError, ValueError) as error:
            self.log(f"Не удалось сохранить настройки: {error}")
            self.help_text.set(f"Ошибка сохранения: {error}")

    def chart_changed(self):
        self.plot_dirty = True
        self.safe_persist()

    def vector_changed(self):
        if not self.vector_enabled.get() and self.calibration.collector.running:
            self.calibration.stop('Рулетка выключена. Запись точек остановлена.')
        if not self.vector_enabled.get() and self.workers["vector"] and self.workers["vector"].alive:
            self.workers["vector"].stop()
            self.vector_current = False
        self._axis_options()
        self.chart_changed()

    def toggle_selector(self):
        if self.selector_visible:
            self.selector.grid_remove()
        else:
            self.selector.grid()
        self.selector_visible = not self.selector_visible

    def emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            try:
                self.events.put_nowait(event)
            except queue.Full:
                pass

    def toggle(self, source):
        worker = self.workers[source]
        button = self.fpga_button if source == "fpga" else self.vector_button
        if worker and worker.alive:
            if self.calibration.collector.running:
                self.calibration.stop('Опрос остановлен пользователем. Точки сохранены.')
            worker.stop()
            button.configure(text="Остановка…", state="disabled")
            return
        if self.closing or source == "vector" and not self.vector_enabled.get():
            return
        self.safe_persist()
        self.workers[source] = DeviceWorker(source, self.settings, self.emit, self.demo, self.log_base)
        button.configure(text="Остановить FPGA" if source == "fpga" else "Остановить рулетку")
        if source == "fpga":
            self.rate_times.clear()
        self.workers[source].start()

    def start_demo(self):
        self.vector_enabled.set(True)
        self.selected["vector_mm"].set(True)
        self._axis_options()
        self.toggle("fpga")
        self.toggle("vector")

    def log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now():%H:%M:%S}  {text}\n")
        if int(self.log_text.index("end-1c").split(".")[0]) > 180:
            self.log_text.delete("1.0", "30.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def handle(self, event):
        source, kind, stamp = event["source"], event["kind"], event["monotonic"]
        t = stamp - self.origin
        if kind == 'dds_busy':
            self.dds_pending = True
            self.dds_controls(False)
            self.fpga_current = False
            self.history.add_fpga(t, {'valid':False, 'fresh':False})
            self.plot_dirty = True
            self.dds_message.set('Обмен DDS: ожидание подтверждения FPGA…')
        elif kind == 'dds_result':
            self.dds_pending = False
            self.active_config = event['config']
            self.show_active_dds()
            worker = self.workers['fpga']
            self.dds_controls(not worker or worker.polling)
            if event['error']:
                text = 'Операция не подтверждена: '+event['error']+'. Повторное обновление автоматически не отправлялось.'
            elif event['action'] == 'apply':
                text = 'Четыре канала синхронно обновлены; активный банк FPGA совпал с отправленным.'
            else:
                text = 'Активный банк FPGA прочитан. Поля ввода не изменены.'
            if self.demo:text = 'ДЕМОНСТРАЦИЯ · '+text
            self.dds_message.set(text)
            self.log('DDS: '+text)
        elif kind == "sample" and source == "fpga":
            row = dict(event["row"])
            self.distance_result = estimate_distance(self.distance_model, row)
            row['phase_distance_mm'] = self.distance_result['distance_mm']
            row['phase_distance_valid'] = self.distance_result['valid']
            row['distance_calibration_id'] = self.distance_model['id'] if self.distance_model else None
            self.last_fpga, self.last_fpga_at = row, stamp
            self.fpga_current = bool(row.get("valid") and row.get('fresh'))
            self.history.add_fpga(t, row)
            self.rate_times.append(stamp)
            self.rate_times = [x for x in self.rate_times if stamp - x < 2]
            rate = (len(self.rate_times) - 1) / max(.001, self.rate_times[-1] - self.rate_times[0])
            self.connection_text.set(f"FPGA {rate:.1f} Гц · пакетов {event['packets']} · CRC {event['crc']} · тайм-аутов {event['timeouts']}")
            self.last_packets = event["packets"]
            diag = row.get("diagnostics", 0)
            self.state_text.set("ДЕМОНСТРАЦИЯ" if self.demo else (f"Достоверно · диагностика 0x{diag:02X}" if self.fpga_current and diag else "Достоверно" if self.fpga_current else "Нет достоверного сигнала"))
            self.badge.configure(foreground=AMBER if diag else ACCENT if self.fpga_current else RED)
            self.plot_dirty = True
        elif kind == "sample":
            distance = event["distance_mm"]
            self.last_vector, self.last_vector_at, self.vector_current = distance, stamp, True
            self.history.add_vector(t, distance, max_age=max(.1, self.settings["fpga_interval_ms"] / 1000 * 2))
            self.plot_dirty = True
        elif kind in ("timeout", "error", "stopped"):
            if source == "fpga":
                self.fpga_current = False
                self.history.add_fpga(t, {"valid": False})
                self.state_text.set("ДЕМОНСТРАЦИЯ" if self.demo else "Опрос остановлен" if kind == "stopped" else "Нет ответа FPGA")
                self.connection_text.set("FPGA: опрос остановлен" if kind == "stopped" else "FPGA: нет актуального ответа")
            else:
                self.vector_current = False
                self.history.add_vector(t, None)
            self.plot_dirty = True
            if kind == "stopped":
                if source == 'fpga':
                    if self.dds_pending:
                        self.dds_message.set('Обмен прерван. Состояние DDS нужно проверить кнопкой «Прочитать FPGA».')
                    self.dds_pending = False
                    self.dds_controls(True)
                    self.dds_active_text.set('Последние DDS платы · соединение закрыто' +
                        (f" · поколение {self.active_config['generation']}" if self.active_config else ''))
                button = self.fpga_button if source == "fpga" else self.vector_button
                button.configure(text="Запустить FPGA" if source == "fpga" else "Запустить рулетку", state="normal" if source == "fpga" or self.vector_enabled.get() else "disabled")
                self.log("Опрос FPGA остановлен, порт закрыт." if source == "fpga" else "Опрос Vector60 остановлен, подключение освобождено.")
            else:
                self.log(event["message"])
        elif kind == "status":
            self.log(event["message"])
        elif kind == "log":
            self.log("Данные сеанса: " + event["path"])
        self.calibration.handle(event)

    def install_distance_model(self, model):
        # Commit to disk before replacing the working model; a failed save is harmless.
        self.distance_store.save(model)
        self.distance_model, self.distance_warning = model, ''
        self.distance_result = estimate_distance(model, self.last_fpga or {})
        if self.last_fpga:
            self.last_fpga['phase_distance_mm'] = self.distance_result['distance_mm']
            self.last_fpga['phase_distance_valid'] = self.distance_result['valid']
        # Keep raw history but break the derived curve at a calibration change.
        self.history.add_fpga(time.monotonic()-self.origin, {'valid':False, 'fresh':False})
        self.plot_dirty = True
        self.log('Коэффициенты расстояния рассчитаны и сохранены: '+str(self.distance_store.path))
        self.render_values()

    def render_values(self):
        row = self.last_fpga or {}
        for key, var in self.card_vars.items():
            if key == "vector_mm":
                value = self.last_vector if self.vector_current else None
                var.set(f"{value:.1f} мм" if value is not None else "—")
            elif key == 'phase_distance_mm':
                value = self.distance_result['distance_mm'] if self.fpga_current and self.distance_result['valid'] else None
                var.set(f'{value:.0f} мм' if value is not None else '—')
                reason = self.distance_result['reason'] if self.fpga_current or not self.distance_model else 'invalid_signal'
                self.distance_status.set(REASONS[reason])
            else:
                value = row.get(key) if self.fpga_current else None
                var.set(f"{value:.3f}°" if value is not None else "—")
        for key in self.table.get_children():
            if key.startswith("fpga_"):
                continue
            value = self.last_vector if key == "vector_mm" else row.get(key)
            if key == "valid":
                text = "Да" if self.fpga_current else "Нет / неактуально"
            elif key == 'phase_distance_mm':
                value = self.distance_result['distance_mm'] if self.fpga_current and self.distance_result['valid'] else None
                text = f'{value:.3f}' if value is not None else '— · '+self.distance_status.get()
            elif key in ("diagnostics", "adc_ok") and value is not None:
                text = f"0x{value:02X}" + (" · сохранённое переполнение CDC" if key == "diagnostics" and value & 4 else "")
            elif isinstance(value, bool):
                text = "Да" if value else "Нет"
            elif isinstance(value, float):
                text = f"{value:.6f}"
            else:
                text = "—" if value is None else str(value)
            if key == "vector_mm" and value is not None and not self.vector_current:
                text += " · историческое"
            self.table.set(key, "value", text)
        if self.last_fpga_at:
            self.values_caption.configure(text=f"Последний ответ FPGA: {time.monotonic() - self.last_fpga_at:.1f} с назад · " + ("актуален" if self.fpga_current else "исторические / недостоверные значения"))

    def draw_chart(self):
        selected = [k for k, v in self.selected.items() if v.get() and (k != "vector_mm" or self.vector_enabled.get())]
        axis = "distance" if self.axis.get() == "Расстояние, мм" else "time"
        signature = (tuple(selected), axis)
        if signature != self.plot_signature:
            self.figure.clear()
            self.lines, self.axes = {}, {}
            units = list(dict.fromkeys(FIELD_MAP[k][1] for k in selected))
            for n, unit in enumerate(units):
                ax = self.figure.add_subplot(len(units), 1, n + 1)
                ax.set_facecolor(PANEL)
                ax.grid(alpha=.2, color=MUTED)
                ax.tick_params(colors=MUTED, labelsize=8)
                for spine in ax.spines.values():
                    spine.set_color("#dfd8cd")
                ax.set_ylabel(unit, color=INK, fontsize=10)
                if n == len(units) - 1:
                    ax.set_xlabel("Расстояние Vector60, мм" if axis == "distance" else "Время от начала графика, с", color=INK, fontsize=9)
                for key in [k for k in selected if FIELD_MAP[k][1] == unit]:
                    color = COLORS[[f[0] for f in FIELDS].index(key) % len(COLORS)]
                    line, = ax.plot([], [], label=FIELD_MAP[key][0], color=color, linewidth=1.4, marker="." if axis == "distance" or key == "vector_mm" else None, markersize=4)
                    self.lines[key] = line
                ax.legend(loc="upper left", fontsize=8, framealpha=.85, ncol=2)
                self.axes[unit] = ax
            if not selected:
                self.figure.text(.5, .5, "Выберите параметры в списке справа", ha="center", va="center", color=MUTED, fontsize=13)
            self.plot_signature = signature
        available = 0
        for key, line in self.lines.items():
            x, y = self.history.series(key, axis, self.settings["history_s"])
            line.set_data(x, y)
            available += sum(math.isfinite(xx) and math.isfinite(yy) for xx, yy in zip(x, y))
        for ax in self.axes.values():
            ax.relim()
            ax.autoscale_view()
            ax.margins(x=.03, y=.12)
        note = f"Автомасштаб · история {self.settings['history_s']} с"
        if axis == "distance":
            note += " · свежие пары по времени получения; без интерполяции"
        if not available:
            note += " · ожидаются данные" if axis == "time" else " · пока нет подходящих пар ответов"
        self.chart_note.set(note)
        self.canvas.draw_idle()
        self.plot_dirty = False

    def clear_chart(self):
        self.history = History()
        self.origin = time.monotonic()
        self.plot_dirty = True

    def tick(self):
        if self.closing:
            return
        for _ in range(2000):
            try:
                self.handle(self.events.get_nowait())
            except queue.Empty:
                break
        now = time.monotonic()
        fpga_age_limit = max(.15, (self.settings["fpga_interval_ms"] + self.settings["fpga_timeout_ms"]) / 1000 + .1)
        if self.fpga_current and self.last_fpga_at and now - self.last_fpga_at > fpga_age_limit:
            self.fpga_current = False
            self.history.add_fpga(now - self.origin, {"valid": False})
            self.state_text.set("Ответ FPGA устарел")
            self.plot_dirty = True
            if self.calibration.collector.running:
                self.calibration.collector.reset('Ответ FPGA устарел. Счётчик трёх показаний сброшен.')
        vector_age_limit = self.settings["vector_interval_s"] + self.settings["vector_timeout_s"]
        if self.vector_current and self.last_vector_at and now - self.last_vector_at > vector_age_limit:
            self.vector_current = False
            self.history.add_vector(now - self.origin, None)
            self.plot_dirty = True
            if self.calibration.collector.running:
                self.calibration.collector.reset('Ответ рулетки устарел. Счётчик трёх показаний сброшен.')
        self.render_values()
        self.calibration.tick(now)
        if self.plot_dirty and now - self.last_plot >= .5:
            self.draw_chart()
            self.last_plot = now
        self.root.after(60, self.tick)

    def save_dds(self):
        try:
            self.persist(include_dds=True)
            self.dds_message.set("Параметры DDS проверены и сохранены на ПК. Состояние платы не менялось.")
            return True
        except (ValueError, OSError, KeyError) as error:
            self.dds_message.set(str(error))
            messagebox.showerror("Параметры DDS", str(error), parent=self.root)
            return False

    def apply_dds(self):
        if self.save_dds():
            self.dds_command('apply', dds_channels(self.settings['dds']))

    def dds_controls(self, enabled):
        for button in (self.dds_apply_button, self.dds_read_button):
            button.configure(state='normal' if enabled else 'disabled')

    def dds_preview(self):
        if len(self.dds_vars) != 4 or not hasattr(self,'dds_if_vars'):return
        rows = [{k:v.get() for k,v in row.items()} for row in self.dds_vars]
        try:
            for band,value in dds_intermediate_frequencies(rows).items():
                self.dds_if_vars[band].set(f'{value:.6f}')
        except (ValueError,KeyError):
            for variable in self.dds_if_vars.values():variable.set('—')
        try:
            channels = dds_channels(rows)
            name = PROFILE_NAME if channels == PROFILE_CHANNELS else 'Пользовательские параметры'
            self.dds_profile_text.set(name)
        except (ValueError, KeyError) as error:
            self.dds_profile_text.set(str(error))

    def restore_dds_profile(self):
        for variables, values in zip(self.dds_vars, DEFAULTS['dds']):
            for key,value in values.items():variables[key].set(format(value, '.12g'))
        self.save_dds()

    def show_active_dds(self):
        config = self.active_config
        if not config:
            self.dds_active_text.set('Активный банк FPGA неизвестен. Повторите чтение.')
            for i in range(4):self.dds_active_table.item(str(i), values=(f'CH{i}','—','—','—'))
            return
        for i, ch in enumerate(config['channels']):
            self.dds_active_table.item(str(i), values=(f'CH{i}', f"{ch['ftw']*500_000_000/2**32:.6f}", f"{ch['phase_word']*360/16384:.6f}", ch['amplitude']))
        prefix = 'ДЕМОНСТРАЦИЯ · ' if self.demo else ''
        self.dds_active_text.set(prefix+f"Банк FPGA прочитан · поколение {config['generation']} · "+('обновление ещё выполняется' if config['configuring'] else 'обновление завершено'))

    def dds_command(self, action, channels=None):
        if self.dds_pending or self.closing:return
        if self.calibration.collector.running and action == 'apply':
            self.dds_message.set('Перед изменением DDS остановите калибровку. Новому профилю нужна отдельная серия.')
            return
        worker = self.workers['fpga']
        if worker and worker.alive and (worker.stop_event.is_set() or not worker.polling):
            self.dds_message.set('Дождитесь завершения текущего обмена с COM-портом.')
            return
        start = not worker or not worker.alive
        if start:
            worker = DeviceWorker('fpga', self.settings, self.emit, self.demo, self.log_base, polling=False)
            self.workers['fpga'] = worker
        worker.submit(action, channels)
        self.dds_pending = True
        self.dds_controls(False)
        self.fpga_current = False
        self.dds_message.set('Запрос DDS поставлен в очередь COM-порта…')
        if start:
            self.fpga_button.configure(state='disabled')
            worker.start()

    def export_chart(self):
        name = filedialog.asksaveasfilename(parent=self.root, title="Сохранить график", defaultextension=".png", filetypes=[("Изображение PNG", "*.png")])
        if name:
            try:
                self.figure.savefig(name, dpi=170)
                self.log("График сохранён: " + name)
            except OSError as error:
                messagebox.showerror("Сохранение графика", str(error), parent=self.root)

    def preferences(self):
        if any(w and w.alive for w in self.workers.values()):
            messagebox.showinfo("Настройки", "Остановите опрос приборов перед изменением подключения и таймеров.", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title("Настройки подключения и опроса")
        win.transient(self.root)
        win.resizable(False, False)
        win.configure(bg=BG)
        body = ttk.Frame(win, padding=22)
        body.pack(fill="both", expand=True)
        variables = {}
        parity_names = {"Нет": "N", "Чётная": "E", "Нечётная": "O", "Маркер": "M", "Пробел": "S"}
        reverse_parity = {v: k for k, v in parity_names.items()}
        try:
            from serial.tools.list_ports import comports
            ports = sorted(set([self.settings["port"]] + [p.device for p in comports()]))
        except Exception:
            ports = [self.settings["port"]]
        items = [
            ("port", "COM-порт", ports, "Выберите порт своего USB–TTL адаптера FPGA. Список определяется на этом компьютере."),
            ("baud", "Скорость, бод", [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600], "Прошивка v3 использует 115200 бод. Настройка программы не меняет скорость FPGA."),
            ("bits", "Биты данных", [5, 6, 7, 8], "Текущая прошивка: 8 бит данных."),
            ("parity", "Чётность", list(parity_names), "Текущая прошивка: без чётности."),
            ("stop_bits", "Стоповые биты", [1, 1.5, 2], "Текущая прошивка: один стоповый бит."),
            ("fpga_interval_ms", "Период опроса FPGA, мс", None, "Минимальный интервал между запросами. UART v3: 12 + 112 байт, при 115200 бод физический предел меньше 93 ответов/с. Запросы не накладываются."),
            ("fpga_timeout_ms", "Тайм-аут FPGA, мс", None, "Время ожидания ответа с нужным идентификатором и правильной CRC."),
            ("vector_address", "Bluetooth-адрес Vector60", None, "Адрес вашей рулетки, полученный сканированием. Для работы только с FPGA можно оставить пустым."),
            ("vector_usb_transport", "USB-адаптер (usb:VID:PID)", None, "Выделенный Bluetooth USB-адаптер с WinUSB. Проверен ASUS 0B05:1D70; другие модели требуют проверки."),
            ("vector_interval_s", "Период опроса Vector60, с", None, "Следующий запрос только после ответа или тайм-аута. При длинном ответе реальный период будет больше."),
            ("vector_timeout_s", "Тайм-аут Vector60, с", None, "По умолчанию 3 секунды на ответ. Подключение Bluetooth имеет отдельное время ожидания."),
            ("history_s", "История графика, с", None, "Показ последних данных, максимум 20000 записей каждого источника. Полный журнал сохраняется отдельно."),
        ]
        for row, (key, label, options, help_text) in enumerate(items):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=6)
            var = tk.StringVar(value=reverse_parity[self.settings[key]] if key == "parity" else str(self.settings[key]))
            variables[key] = var
            widget = ttk.Combobox(body, textvariable=var, values=options, width=27, state="normal" if key == "port" else "readonly") if options else ttk.Entry(body, textvariable=var, width=29)
            widget.grid(row=row, column=1, sticky="ew", pady=6)
            self.hint(widget, help_text)
        def apply():
            try:
                candidate = deepcopy(self.settings)
                candidate.update({k: v.get() for k, v in variables.items()})
                candidate["parity"] = parity_names[candidate["parity"]]
                candidate["bits"], candidate["stop_bits"] = int(candidate["bits"]), float(candidate["stop_bits"])
                checked = validate_settings(candidate)
                self.store.save(checked)
                self.settings = checked
                self.saved_serialized = json.dumps(checked, sort_keys=True)
                self._port_caption()
                self.plot_dirty = True
                win.destroy()
                self.log("Настройки подключения и таймеров сохранены.")
            except (ValueError, OSError, KeyError) as error:
                messagebox.showerror("Проверьте настройки", str(error), parent=win)
        buttons = ttk.Frame(body)
        buttons.grid(row=len(items), column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Отмена", command=win.destroy).pack(side="left", padx=8)
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton", command=apply).pack(side="left")
        win.update_idletasks()
        win.geometry(f"+{self.root.winfo_x() + max(0, (self.root.winfo_width() - win.winfo_reqwidth()) // 2)}+{self.root.winfo_y() + 60}")
        win.grab_set()

    def close(self):
        if self.closing:
            return
        try:
            self.persist(include_dds=True)
        except ValueError as error:
            self.safe_persist()
            messagebox.showwarning("Параметры DDS не сохранены", f"{error}\nСохранены предыдущие корректные параметры.", parent=self.root)
        except OSError as error:
            messagebox.showerror("Ошибка сохранения", str(error), parent=self.root)
            return
        self.closing = True
        self.calibration.stop()
        self.help_text.set("Завершение опроса и освобождение подключений…")
        for worker in self.workers.values():
            if worker and worker.alive:
                worker.stop()
        self._wait_close()

    def _wait_close(self):
        if any(w and w.alive for w in self.workers.values()):
            self.root.after(100, self._wait_close)
        else:
            for timer in self.root.tk.call('after', 'info'):
                self.root.after_cancel(timer)
            self.root.destroy()

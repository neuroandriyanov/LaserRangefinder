"""Russian calibration tab. Hardware ownership remains in the main application."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import __version__
from .calibration import (CalibrationCollector, CalibrationStore, PHASE_KEYS, REQUIRED_SAMPLES,
                          load_csv_points, verified_csv_source)
from .distance import fit_calibration
from .model import ROOT


class CalibrationTab:
    def __init__(self, parent, app):
        self.app, self.parent = app, parent
        self.collector = CalibrationCollector()
        self.store = None
        self.owned = set()
        self.sources = {}
        self.dirty = True
        self.warning = None
        saved = app.settings.get('calibration_file')
        if saved:
            try:
                self.store, points = CalibrationStore.load(saved)
                if bool(self.store.metadata.get('demo')) != app.demo:
                    raise ValueError('Демонстрационные и реальные серии разделены.')
                self.collector = CalibrationCollector(points)
                self.collector.message = f'Загружено точек: {len(points)}.'
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.store = None
                self.warning = 'Не удалось открыть прошлую серию: '+str(error)
        self.progress = tk.StringVar(value=self.warning or self.collector.message)
        self.file_text = tk.StringVar(value=self.caption())
        self.calculation_text = tk.StringVar(value=self.calculation_caption())
        ttk.Label(parent, text='Калибровка дальномера', style='Panel.TLabel', font=('Segoe UI',18,'bold')).pack(anchor='w')
        controls = ttk.Frame(parent, style='Panel.TFrame');controls.pack(fill='x',pady=(10,0))
        self.start_button = app.hint(ttk.Button(controls, text='Старт калибровки', style='Accent.TButton', command=self.toggle),
            'Запустить запись точек и необходимые приборы. Стоп завершает запись и останавливает опрос, запущенный этой вкладкой.')
        self.start_button.pack(side='left')
        self.new_button = app.hint(ttk.Button(controls,text='Новая серия',command=self.new),
            'Начать отдельный набор точек. Предыдущие файлы остаются на диске.')
        self.new_button.pack(side='left',padx=8)
        app.hint(ttk.Button(controls,text='Экспорт CSV…',command=self.export), 'Сохранить расстояния и четыре фазы записанных точек в CSV.').pack(side='left')
        self.import_button = app.hint(ttk.Button(controls,text='Загрузить CSV…',command=self.import_csv),
            'Открыть сохранённые расстояния и фазы, например cal2.csv. Предыдущая серия остаётся на диске.')
        self.import_button.pack(side='left', padx=8)
        self.calculate_button = app.hint(ttk.Button(controls,text='Рассчитать',command=self.calculate),
            'Рассчитать и сохранить коэффициенты. НЧ выбирает оборот; МНК четвёртой степени по ВЧ даёт расстояние в мм.')
        self.calculate_button.pack(side='right')
        ttk.Label(parent,textvariable=self.progress,style='Panel.TLabel',foreground='#326b59').pack(anchor='w',pady=(10,3))
        calculation_label = ttk.Label(parent,textvariable=self.calculation_text,style='Panel.TLabel',foreground='#778078',wraplength=round(1120*app.scale))
        calculation_label.pack(anchor='w',fill='x',pady=(0,6))
        calculation_label.bind('<Enter>',lambda e:app.help_text.set('Коэффициенты: '+str(app.distance_store.path)+
            '. Серия: '+(str(self.store.path) if self.store else 'не выбрана')+'. RMS подгонки не равен абсолютной погрешности.'))
        calculation_label.bind('<Leave>',lambda e:app.help_text.set('Готово.'))
        panes = ttk.Panedwindow(parent,orient='vertical');panes.pack(fill='both',expand=True)
        top = ttk.Frame(panes,style='Panel.TFrame');bottom = ttk.Frame(panes,style='Panel.TFrame')
        panes.add(top,weight=2);panes.add(bottom,weight=3)
        self.table = ttk.Treeview(top,columns=('index','distance',*PHASE_KEYS),show='headings',height=5)
        for key,title,width in [('index','№',45),('distance','Расстояние, мм',150),
                                *[(key,label,160) for key,label in zip(PHASE_KEYS,('АЦП ВЧ, °','АЦП НЧ, °','Цифровая ВЧ, °','Цифровая НЧ, °'))]]:
            self.table.heading(key,text=title)
            self.table.column(key,width=round(width*app.scale),anchor='w')
        bar = ttk.Scrollbar(top,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        self.figure = Figure(figsize=(8,3),dpi=100,facecolor='#fffcf7',layout='constrained')
        self.canvas = FigureCanvasTkAgg(self.figure,master=bottom)
        self.canvas.get_tk_widget().pack(fill='both',expand=True)
        app.hint(self.canvas.get_tk_widget(),'Записанные точки: X — расстояние рулетки в мм, Y — исходные фазы в градусах. «Рассчитать» сохраняет модель для текущего диапазона.')
        for point in self.collector.points:self.insert(point)

    def caption(self):
        return f'Автосохранение: {self.store.path.parent.name}/points.json' if self.store else 'Новая серия · файл будет создан при старте'

    def calculation_caption(self):
        model = self.app.distance_model
        if not model:
            return self.app.distance_warning or 'Калибровка не рассчитана.'
        lo, hi = model['distance_range_mm']
        p = model['profiles']['analog']
        method = 'МНК 4' if 'fine_mm' in p else 'МНК 3'
        return (f"{method} · {model['point_count']} точек · {lo:.0f}–{hi:.0f} мм · RMS подгонки {p['fit_rms_mm']:.2f} мм"
                + ('' if model.get('dds_channels') else ' · DDS не подтверждены'))

    def create_store(self):
        base = self.app.log_base or (ROOT/'.cache/desktop-demo' if self.app.demo else ROOT/'captures')
        folder = Path(base)/'calibration'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        self.store = CalibrationStore(folder/'points.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
            app_version=__version__,demo=self.app.demo,settings=deepcopy(self.app.settings),
            required_samples=REQUIRED_SAMPLES,
            rule='3 consecutive equal ATD distances at native 0.1 mm resolution; each paired with valid fresh GET started after ATD, within 500 ms; phases from third pair'))
        self.store.save([])
        self.app.settings['calibration_file'] = str(self.store.path)
        self.app.persist()
        self.file_text.set(self.caption())

    def toggle(self):
        if self.collector.running:
            self.stop()
            return
        if any(w and w.alive and w.stop_event.is_set() for w in self.app.workers.values()):
            self.progress.set('Дождитесь завершения остановки приборов.')
            return
        worker = self.app.workers['fpga']
        if self.app.dds_pending or worker and worker.alive and not worker.polling:
            self.progress.set('Дождитесь завершения обмена DDS.')
            return
        if self.store and self.collector.points and (self.store.metadata.get('required_samples') != REQUIRED_SAMPLES or
                                                    not self.store.metadata.get('dds_channels')):
            self.progress.set('Это прежняя или импортированная серия. Для записи по трём ответам нажмите «Новая серия».')
            return
        try:
            if self.store is None:self.create_store()
        except (OSError,ValueError) as error:
            self.progress.set('Не удалось создать файл серии: '+str(error));return
        self.collector.start(time.monotonic())
        self.app.vector_enabled.set(True)
        self.app.vector_changed()
        self.owned.clear()
        for source in ('fpga','vector'):
            worker = self.app.workers[source]
            if not worker or not worker.alive:
                self.owned.add(source)
                self.app.toggle(source)
        self.start_button.configure(text='Остановить калибровку')
        self.new_button.configure(state='disabled')
        self.import_button.configure(state='disabled')
        self.calculate_button.configure(state='disabled')
        self.progress.set(self.collector.message)

    def stop(self, message='Запись точек остановлена. Все принятые точки сохранены.'):
        self.collector.stop(message)
        for source in self.owned:
            worker = self.app.workers[source]
            if worker and worker.alive:worker.stop()
        self.owned.clear()
        self.start_button.configure(text='Старт калибровки')
        self.new_button.configure(state='normal')
        self.import_button.configure(state='normal')
        self.calculate_button.configure(state='normal')
        self.progress.set(message)

    def new(self):
        if self.collector.running:return
        self.collector = CalibrationCollector()
        self.store = None
        self.app.settings['calibration_file'] = ''
        self.app.safe_persist()
        for item in self.table.get_children():self.table.delete(item)
        self.file_text.set(self.caption());self.progress.set(self.collector.message);self.dirty=True
        self.calculation_text.set(self.calculation_caption())

    def insert(self, point):
        self.table.insert('', 'end', values=(point['index'], f"{point['distance_mm']:.1f}",
                                            *[f"{point['phases'][key]:.6f}" for key in PHASE_KEYS]))
        self.table.yview_moveto(1)
        self.dirty = True

    def handle(self, event):
        source,kind,stamp = event['source'],event['kind'],event['monotonic']
        if kind=='log':self.sources[source]=event['path']
        if not self.collector.running or stamp<self.collector.started:return
        if kind in ('timeout','error','stopped'):
            if kind=='stopped':self.stop('Опрос прибора остановлен. Запись точек приостановлена.')
            else:self.collector.reset('Нет достоверного ответа. Счётчик трёх показаний сброшен.')
        elif kind == 'dds_busy':
            self.collector.reset('Чтение или изменение DDS. Ожидание новой серии из трёх ответов.')
        elif kind == 'dds_result' and event.get('error'):
            self.collector.reset('Банк DDS не подтверждён. Ожидание достоверных данных.')
        elif kind=='sample' and source=='vector':
            self.collector.vector(stamp,event['distance_mm'])
        elif kind=='sample' and source=='fpga':
            bank = event['row'].get('dds_channels')
            if not bank or event['row'].get('configuring'):
                self.collector.reset('Нет подтверждённого банка DDS. Точка не записывается.')
                self.progress.set(self.collector.message)
                return
            previous = self.store.metadata.get('dds_channels')
            if previous and previous != bank:
                self.stop('Настройки DDS изменились. Начните новую серию калибровки.')
                return
            if previous is None:
                self.store.metadata['dds_channels'] = deepcopy(bank)
                try:
                    self.store.save(self.collector.points)
                except (OSError, ValueError) as error:
                    self.stop('Банк DDS не сохранён: '+str(error))
                    return
            point = self.collector.fpga(stamp,event.get('request_started'),event['row'])
            if point:
                point['source_logs'] = dict(self.sources)
                try:
                    self.store.save([*self.collector.points,point])
                except (OSError,ValueError) as error:
                    self.stop('Точка НЕ записана: '+str(error))
                    return
                self.collector.commit(point)
                self.insert(point)
                self.calculation_text.set('Точки обновлены. Нажмите «Рассчитать» после остановки.')
                self.app.log(self.collector.message)
                self.beep()
        self.progress.set(self.collector.message)

    def tick(self, now):
        if self.collector.running:
            self.collector.expire(now)
            self.progress.set(self.collector.message)
        if not self.dirty:return
        self.figure.clear()
        for n, keys in enumerate((PHASE_KEYS[::2],PHASE_KEYS[1::2])):
            axis = self.figure.add_subplot(2,1,n+1)
            axis.set_facecolor('#fffcf7');axis.grid(alpha=.2)
            for key,color,label in zip(keys,('#327765','#ae5c68'),('АЦП','Цифровая')):
                points=sorted(self.collector.points,key=lambda p:p['distance_mm'])
                axis.plot([p['distance_mm'] for p in points],[p['phases'][key] for p in points],
                          '.',color=color,label=label,markersize=7)
            axis.set_ylabel('ВЧ, °' if n==0 else 'НЧ, °');axis.legend(fontsize=8,loc='best')
            if n==1:axis.set_xlabel('Расстояние Vector60, мм')
        self.canvas.draw_idle();self.dirty=False

    def beep(self):
        try:
            import winsound
            def tone():
                try:winsound.Beep(1400,160)
                except RuntimeError:pass
            threading.Thread(target=tone,daemon=True).start()
        except ImportError:self.app.root.bell()

    def export(self):
        if not self.store or not self.collector.points:
            self.progress.set('Пока нет записанных точек.');return
        path=filedialog.asksaveasfilename(parent=self.app.root,title='Экспорт точек калибровки',
            defaultextension='.csv',filetypes=[('Таблица CSV','*.csv')])
        if path:
            try:self.store.export_csv(path,self.collector.points)
            except OSError as error:messagebox.showerror('Экспорт CSV',str(error),parent=self.app.root)

    def calculate(self):
        if self.collector.running:
            self.progress.set('Остановите запись точек перед расчётом.');return
        try:
            metadata = self.store.metadata if self.store else {}
            model = fit_calibration(self.collector.points, demo=self.app.demo,
                source=str(self.store.path) if self.store else '',
                dds_settings=metadata.get('settings', {}).get('dds'),
                confirmed_dds=metadata.get('dds_channels'))
            self.app.install_distance_model(model)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.calculation_text.set('Расчёт не применён: '+str(error)+'\nПредыдущая сохранённая модель не изменена.')
            return
        self.calculation_text.set(self.calculation_caption())
        self.progress.set('Коэффициенты рассчитаны и сохранены. ' + (
            'Можно открыть вкладку «Измерения».' if model.get('dds_channels')
            else 'Для применения к UART v3 нужна серия с подтверждённым банком DDS.'))

    def import_csv(self):
        if self.collector.running:return
        path = filedialog.askopenfilename(parent=self.app.root, title='Загрузить точки калибровки',
            initialdir=ROOT/'desktop_app', filetypes=[('Точки CSV','*.csv')])
        if not path:return
        try:
            points = load_csv_points(path)
            base = self.app.log_base or (ROOT/'.cache/desktop-demo' if self.app.demo else ROOT/'captures')
            provenance = {} if self.app.demo else verified_csv_source(points, Path(base)/'calibration')
            folder = Path(base)/'calibration'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
            store = CalibrationStore(folder/'points.json', dict(app_version=__version__, demo=self.app.demo,
                imported_csv=str(path), source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                settings=deepcopy(self.app.settings), rule='Imported CSV phases; raw observations are preserved in the verified source when matched.',
                **provenance))
            store.save(points)
            settings = deepcopy(self.app.settings)
            settings['calibration_file'] = str(store.path)
            self.app.store.save(settings)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.progress.set('CSV не загружен: '+str(error));return
        self.app.settings = settings
        self.store, self.collector = store, CalibrationCollector(points)
        for item in self.table.get_children():self.table.delete(item)
        for point in points:self.insert(point)
        self.file_text.set(self.caption())
        self.progress.set(f'Загружено точек: {len(points)}. Нажмите «Рассчитать».')
        self.calculation_text.set(self.calculation_caption())
        self.app.log('Загружена серия калибровки: '+str(path))

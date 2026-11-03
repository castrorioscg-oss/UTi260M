"""Ventana principal del visor térmico UTi260M."""
import json
import os
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import QRectF, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QImage, QKeySequence,
                           QPainter, QShortcut)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import i18n
from .camera import CameraThread, DemoThread
from .i18n import tr
from .processing import (
    DIFF_LUT, HD_SCALE, MATERIALS, build_palettes, colorize, correct_emissivity, fmt_temp, orient,
    raw_to_celsius, upscale,
)
from .widgets import ColorBar, Section, ThermalView, draw_colorbar

ALARM_HI_RGB = np.array([0, 255, 0], np.uint8)
ALARM_LO_RGB = np.array([0, 255, 255], np.uint8)
SMOOTH_SCALE = 3
DEFAULT_PALETTE = "lava"
SECTIONS = [  # (id, clave de título, desplegada por defecto)
    ("capture", "sec_capture", True),
    ("image", "sec_image", True),
    ("range", "sec_range", False),
    ("material", "sec_material", False),
    ("meas", "sec_meas", False),
    ("alarm", "sec_alarm", False),
    ("compare", "sec_compare", False),
]
HINT_CSS = "color: gray; font-size: 8pt"


def dspin(lo, hi, val, step=0.1, dec=1, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    return s


class MainWindow(QMainWindow):
    def __init__(self, demo=False, index=None):
        super().__init__()
        self.resize(1280, 800)
        self.settings = QSettings("Safegrid", "UTi260M")
        i18n.set_lang(str(self.settings.value("lang", "en")))
        self.palettes = build_palettes()
        self._texts = []            # (setter, clave) para retraducir

        self.base = None            # °C sin corregir, orientación del sensor, promediado
        self.temps = None           # °C corregido y orientado (lo que se mide)
        self.ref_base = None        # referencia para modo diferencial
        self.ref_desc = None        # (clave, kwargs)
        self.ref_collect = None
        self.avg_buf = deque(maxlen=1)
        self.frozen = False
        self.loaded_name = None
        self.rot, self.flip_h, self.flip_v = 0, False, False
        self.lo = self.hi = None
        self.cur_lut = None
        self._last_diff = False
        self.writer = None
        self.rec_path = None
        self.last_beep = 0
        self.last_status = ("st_search", False, -1)
        self.fps_count, self.fps_t0, self.fps = 0, time.time(), 0.0

        self._build_ui()
        self._build_menu()
        self._load_settings()
        self._shortcuts()
        self.retranslate()

        self.table_timer = QTimer(self, interval=250, timeout=self._update_readouts)
        self.table_timer.start()

        if index is None:
            v = self.settings.value("cam_index")
            index = int(v) if v is not None else None
        self.cam = (DemoThread if demo else CameraThread)(index)
        self.cam.frame.connect(self.on_frame)
        self.cam.status.connect(self.on_status)
        self.cam.found_index.connect(lambda i: self.settings.setValue("cam_index", i))
        self.cam.start()

    # ================================================================ helpers i18n
    def _reg(self, setter, key):
        self._texts.append((setter, key))
        setter(tr(key))

    def _label(self, key, hint=False, wrap=False):
        w = QLabel()
        self._reg(w.setText, key)
        if hint:
            w.setStyleSheet(HINT_CSS)
        if wrap:
            w.setWordWrap(True)
        return w

    def _button(self, key, checkable=False, tip=None):
        w = QPushButton()
        self._reg(w.setText, key)
        w.setCheckable(checkable)
        if tip:
            self._reg(w.setToolTip, tip)
        return w

    def _check(self, key):
        w = QCheckBox()
        self._reg(w.setText, key)
        return w

    def retranslate(self):
        self.setWindowTitle(tr("title"))
        for setter, key in self._texts:
            setter(tr(key))
        for i, pid in enumerate(self.palettes):
            self.cmb_pal.setItemText(i, tr("pal_" + pid))
        for i, (key, e) in enumerate(MATERIALS):
            self.cmb_mat.setItemText(i, tr(key) if e is None else f"{tr(key)}  (ε {e:.2f})")
        for i in range(4):
            self.cmb_hd.setItemText(i, tr(f"hd_{i}"))
        self.table.setHorizontalHeaderLabels(["", tr("col_val"), tr("min"), tr("avg_s")])
        self.btn_rec.setText(tr("rec_stop") if self.writer is not None else tr("rec"))
        if self.ref_collect is None:
            self.btn_ref.setText(tr("take_ref"))
        self.lbl_ref.setText(tr("ref_is", d=tr(self.ref_desc[0], **self.ref_desc[1]))
                             if self.ref_desc else tr("no_ref"))
        self.on_status(*self.last_status)
        self._update_readouts()
        self.render()

    def set_language(self, lang):
        i18n.set_lang(lang)
        self.settings.setValue("lang", lang)
        self.retranslate()

    # ================================================================ UI
    def _section(self, sid, key, expanded):
        s = Section("", expanded)
        self._reg(s.setTitle, key)
        self.sections[sid] = s
        self.panel_layout.addWidget(s)
        g = QGridLayout(s.body)
        g.setContentsMargins(6, 2, 4, 6)
        return g

    def _build_ui(self):
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        self.view = ThermalView()
        self.view.hover.connect(self._on_hover)
        self.view.rois_changed.connect(self._update_readouts)
        self.cbar = ColorBar()
        lay.addWidget(self.view, 1)
        lay.addWidget(self.cbar)

        panel = QWidget()
        self.panel_layout = QVBoxLayout(panel)
        self.panel_layout.setContentsMargins(2, 2, 2, 2)
        self.panel_layout.setSpacing(3)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(scroll)
        self.setCentralWidget(central)
        self.sections = {}
        sec = {sid: (key, exp) for sid, key, exp in SECTIONS}

        # ---- Captura
        gl = self._section("capture", *sec["capture"])
        self.btn_photo = self._button("photo")
        self.btn_photo.clicked.connect(self.snapshot)
        self.btn_rec = self._button("rec", checkable=True)
        self.btn_rec.toggled.connect(self.toggle_record)
        self.btn_freeze = self._button("freeze", checkable=True)
        self.btn_freeze.toggled.connect(self.toggle_freeze)
        btn_open = self._button("open")
        btn_open.clicked.connect(self.open_capture)
        btn_dir = self._button("folder")
        btn_dir.clicked.connect(self.choose_folder)
        btn_show = self._button("show_folder")
        btn_show.clicked.connect(self.show_folder)
        self.lbl_folder = QLabel()
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setStyleSheet(HINT_CSS)
        self.lbl_folder.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        gl.addWidget(self.btn_photo, 0, 0, 1, 2)
        gl.addWidget(self.btn_rec, 1, 0)
        gl.addWidget(self.btn_freeze, 1, 1)
        gl.addWidget(btn_open, 2, 0)
        gl.addWidget(btn_dir, 2, 1)
        gl.addWidget(btn_show, 3, 0)
        gl.addWidget(self.lbl_folder, 4, 0, 1, 2)

        # ---- Imagen
        gl = self._section("image", *sec["image"])
        self.cmb_pal = QComboBox()
        for pid in self.palettes:
            self.cmb_pal.addItem(pid, pid)
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItems(["°C", "°F", "K"])
        self.cmb_hd = QComboBox()
        self.cmb_hd.addItems(["0", "1", "2", "3"])
        self._reg(self.cmb_hd.setToolTip, "hd_tip")
        self.chk_smooth = self._check("smooth")
        self.spn_avg = QSpinBox()
        self.spn_avg.setRange(1, 32)
        self._reg(self.spn_avg.setToolTip, "avg_tip")
        btn_rot = self._button("rotate")
        btn_rot.clicked.connect(self._rotate)
        self.chk_fh = self._check("mirror_h")
        self.chk_fv = self._check("mirror_v")
        gl.addWidget(self._label("palette"), 0, 0)
        gl.addWidget(self.cmb_pal, 0, 1, 1, 2)
        gl.addWidget(self._label("hd"), 1, 0)
        gl.addWidget(self.cmb_hd, 1, 1)
        gl.addWidget(self.chk_smooth, 1, 2)
        gl.addWidget(self._label("unit"), 2, 0)
        gl.addWidget(self.cmb_unit, 2, 1)
        gl.addWidget(self._label("avg"), 3, 0)
        gl.addWidget(self.spn_avg, 3, 1)
        gl.addWidget(self._label("frames"), 3, 2)
        gl.addWidget(btn_rot, 4, 0)
        gl.addWidget(self.chk_fh, 4, 1)
        gl.addWidget(self.chk_fv, 4, 2)

        # ---- Rango
        gl = self._section("range", *sec["range"])
        self.rb_auto = QRadioButton()
        self._reg(self.rb_auto.setText, "auto")
        self.rb_man = QRadioButton()
        self._reg(self.rb_man.setText, "manual")
        self.rb_auto.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_auto)
        bg.addButton(self.rb_man)
        self.spn_lo = dspin(-40, 600, 20)
        self.spn_hi = dspin(-40, 600, 60)
        btn_lock = self._button("lock", tip="lock_tip")
        btn_lock.clicked.connect(self._lock_range)
        gl.addWidget(self.rb_auto, 0, 0)
        gl.addWidget(self.rb_man, 0, 1)
        gl.addWidget(btn_lock, 0, 2)
        gl.addWidget(self._label("min"), 1, 0)
        gl.addWidget(self.spn_lo, 1, 1)
        gl.addWidget(self._label("max"), 2, 0)
        gl.addWidget(self.spn_hi, 2, 1)

        # ---- Emisividad
        gl = self._section("material", *sec["material"])
        self.cmb_mat = QComboBox()
        for key, _ in MATERIALS:
            self.cmb_mat.addItem(key)
        self.cmb_mat.currentIndexChanged.connect(self._material_changed)
        self.spn_eps = dspin(0.01, 1.0, 0.95, 0.01, 2)
        self.spn_eps.valueChanged.connect(self._eps_edited)
        self.spn_trefl = dspin(-40, 200, 25, 0.5, 1, " °C")
        self._reg(self.spn_trefl.setToolTip, "trefl_tip")
        gl.addWidget(self.cmb_mat, 0, 0, 1, 2)
        gl.addWidget(self._label("eps"), 1, 0)
        gl.addWidget(self.spn_eps, 1, 1)
        gl.addWidget(self._label("trefl"), 2, 0)
        gl.addWidget(self.spn_trefl, 2, 1)
        gl.addWidget(self._label("metal_hint", hint=True, wrap=True), 3, 0, 1, 2)

        # ---- Mediciones
        gl = self._section("meas", *sec["meas"])
        self.chk_max = self._check("max")
        self.chk_min = self._check("min")
        self.chk_ctr = self._check("center")
        btn_clr = self._button("clear")
        btn_clr.clicked.connect(self.view.clear_rois)
        self.table = QTableWidget(0, 4)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(140)
        gl.addWidget(self.chk_max, 0, 0)
        gl.addWidget(self.chk_min, 0, 1)
        gl.addWidget(self.chk_ctr, 0, 2)
        gl.addWidget(btn_clr, 0, 3)
        gl.addWidget(self._label("meas_hint", hint=True, wrap=True), 1, 0, 1, 4)
        gl.addWidget(self.table, 2, 0, 1, 4)

        # ---- Alarma
        gl = self._section("alarm", *sec["alarm"])
        self.chk_ahi = self._check("a_hi")
        self.spn_ahi = dspin(-40, 600, 70, 0.5, 1, " °C")
        self.chk_alo = self._check("a_lo")
        self.spn_alo = dspin(-40, 600, 10, 0.5, 1, " °C")
        self.chk_beep = self._check("sound")
        sw_hi = self._label("green")
        sw_hi.setStyleSheet("color: rgb(0,220,0)")
        sw_lo = self._label("cyan")
        sw_lo.setStyleSheet("color: rgb(0,200,220)")
        gl.addWidget(self.chk_ahi, 0, 0)
        gl.addWidget(self.spn_ahi, 0, 1)
        gl.addWidget(sw_hi, 0, 2)
        gl.addWidget(self.chk_alo, 1, 0)
        gl.addWidget(self.spn_alo, 1, 1)
        gl.addWidget(sw_lo, 1, 2)
        gl.addWidget(self.chk_beep, 2, 0)

        # ---- Diferencial
        gl = self._section("compare", *sec["compare"])
        self.btn_ref = self._button("take_ref", tip="take_ref_tip")
        self.btn_ref.clicked.connect(self.take_reference)
        btn_lref = self._button("load_ref")
        btn_lref.clicked.connect(self.load_reference)
        btn_sref = self._button("save_ref")
        btn_sref.clicked.connect(self.save_reference)
        self.chk_diff = self._check("show_diff")
        self.chk_dauto = self._check("auto_scale")
        self.chk_dauto.setChecked(True)
        self.spn_dspan = dspin(0.2, 100, 5, 0.5, 1, " °C")
        self.lbl_ref = QLabel()
        self.lbl_ref.setStyleSheet(HINT_CSS)
        gl.addWidget(self.btn_ref, 0, 0, 1, 2)
        gl.addWidget(btn_lref, 1, 0)
        gl.addWidget(btn_sref, 1, 1)
        gl.addWidget(self.chk_diff, 2, 0, 1, 2)
        gl.addWidget(self.chk_dauto, 3, 0)
        gl.addWidget(self.spn_dspan, 3, 1)
        gl.addWidget(self.lbl_ref, 4, 0, 1, 2)
        gl.addWidget(self._label("diff_info", hint=True, wrap=True), 5, 0, 1, 2)
        self.panel_layout.addStretch(1)

        # ---- barra de estado
        self.lbl_status = QLabel()
        self.lbl_stats = QLabel()
        self.lbl_hover = QLabel()
        self.lbl_alarm = QLabel()
        self.lbl_alarm.setStyleSheet("color: white; background: #c00; font-weight: bold; padding: 0 6px")
        self.lbl_alarm.hide()
        sb = self.statusBar()
        sb.addWidget(self.lbl_status)
        sb.addWidget(self.lbl_stats, 1)
        sb.addPermanentWidget(self.lbl_alarm)
        sb.addPermanentWidget(self.lbl_hover)

        # re-render con cualquier cambio
        for w in (self.cmb_pal, self.cmb_unit, self.cmb_hd):
            w.currentIndexChanged.connect(self.render)
        for w in (self.chk_smooth, self.chk_max, self.chk_min, self.chk_ctr, self.rb_auto,
                  self.chk_ahi, self.chk_alo, self.chk_diff, self.chk_dauto):
            w.toggled.connect(self.render)
        for w in (self.spn_lo, self.spn_hi, self.spn_trefl, self.spn_ahi, self.spn_alo, self.spn_dspan):
            w.valueChanged.connect(self.render)
        self.cmb_hd.currentIndexChanged.connect(lambda i: self.chk_smooth.setEnabled(i == 0))
        self.chk_fh.toggled.connect(self._orientation_changed)
        self.chk_fv.toggled.connect(self._orientation_changed)
        self.spn_avg.valueChanged.connect(self._avg_changed)
        self.chk_diff.toggled.connect(self._diff_toggled)

    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("")
        self._reg(m.setTitle, "m_file")
        for key, fn, sc in (("m_snapshot", self.snapshot, None), ("m_open", self.open_capture, "Ctrl+O"),
                            ("m_folder", self.show_folder, None), (None, None, None),
                            ("m_exit", self.close, "Ctrl+Q")):
            if key is None:
                m.addSeparator()
                continue
            a = QAction(self)
            self._reg(a.setText, key)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            m.addAction(a)
        m = mb.addMenu("")
        self._reg(m.setTitle, "m_lang")
        grp = QActionGroup(self)
        grp.setExclusive(True)
        self.lang_actions = {}
        for code, name in i18n.LANGS.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == i18n.lang())
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            grp.addAction(a)
            m.addAction(a)
            self.lang_actions[code] = a

    def _shortcuts(self):
        for key, fn in (("Space", self.snapshot), ("F", self.btn_freeze.toggle),
                        ("R", self.btn_rec.toggle), ("Delete", self.view.clear_rois),
                        ("D", self.chk_diff.toggle)):
            QShortcut(QKeySequence(key), self, activated=fn)

    # ================================================================ ajustes
    def _load_settings(self):
        """Paleta (Lava), rango (automático) y alarmas (apagadas) siempre parten por defecto."""
        s = self.settings
        g = lambda k, d, t=str: t(s.value(k, d))
        b = lambda k, d: str(s.value(k, d)).lower() in ("true", "1")
        self.cmb_pal.setCurrentIndex(self.cmb_pal.findData(DEFAULT_PALETTE))
        self.rb_auto.setChecked(True)
        self.chk_ahi.setChecked(False)
        self.chk_alo.setChecked(False)
        self.cmb_unit.setCurrentText(g("unit", "°C"))
        self.cmb_hd.setCurrentIndex(g("hd", 2, int))
        self.chk_smooth.setChecked(b("smooth", True))
        self.chk_smooth.setEnabled(self.cmb_hd.currentIndex() == 0)
        self.spn_avg.setValue(g("avg", 2, int))
        self.avg_buf = deque(maxlen=self.spn_avg.value())
        self.rot = g("rot", 0, int)
        self.chk_fh.setChecked(b("flip_h", False))
        self.chk_fv.setChecked(b("flip_v", False))
        self.cmb_mat.setCurrentIndex(g("material", 1, int))
        self.spn_eps.setValue(g("eps", 0.92, float))
        self.spn_trefl.setValue(g("trefl", 25.0, float))
        self.chk_max.setChecked(b("show_max", True))
        self.chk_min.setChecked(b("show_min", True))
        self.chk_ctr.setChecked(b("show_ctr", True))
        self.spn_ahi.setValue(g("alarm_hi_v", 70.0, float))
        self.spn_alo.setValue(g("alarm_lo_v", 10.0, float))
        self.chk_beep.setChecked(b("beep", False))
        self.spn_lo.setValue(g("range_lo", 20.0, float))
        self.spn_hi.setValue(g("range_hi", 60.0, float))
        for sid, _, exp in SECTIONS:
            self.sections[sid].setExpanded(b(f"sec_{sid}", exp))
        default_dir = os.path.join(os.path.expanduser("~"), "Pictures", "UTi260M")
        self.folder = g("folder", default_dir)
        self.lbl_folder.setText(self.folder)

    def _save_settings(self):
        s = self.settings
        vals = {
            "unit": self.cmb_unit.currentText(), "hd": self.cmb_hd.currentIndex(),
            "smooth": self.chk_smooth.isChecked(), "avg": self.spn_avg.value(), "rot": self.rot,
            "flip_h": self.chk_fh.isChecked(), "flip_v": self.chk_fv.isChecked(),
            "material": self.cmb_mat.currentIndex(), "eps": self.spn_eps.value(),
            "trefl": self.spn_trefl.value(), "show_max": self.chk_max.isChecked(),
            "show_min": self.chk_min.isChecked(), "show_ctr": self.chk_ctr.isChecked(),
            "alarm_hi_v": self.spn_ahi.value(), "alarm_lo_v": self.spn_alo.value(),
            "beep": self.chk_beep.isChecked(), "range_lo": self.spn_lo.value(),
            "range_hi": self.spn_hi.value(), "folder": self.folder, "lang": i18n.lang(),
        }
        vals.update({f"sec_{sid}": sec.isExpanded() for sid, sec in self.sections.items()})
        for k, v in vals.items():
            s.setValue(k, v)

    # ================================================================ eventos de controles
    def _material_changed(self, i):
        e = MATERIALS[i][1]
        if e is not None:
            self.spn_eps.blockSignals(True)
            self.spn_eps.setValue(e)
            self.spn_eps.blockSignals(False)
        self.render()

    def _eps_edited(self, v):
        e = MATERIALS[self.cmb_mat.currentIndex()][1]
        if e is not None and abs(e - v) > 1e-6:
            self.cmb_mat.blockSignals(True)
            self.cmb_mat.setCurrentIndex(0)
            self.cmb_mat.blockSignals(False)
        self.render()

    def _rotate(self):
        self.rot = (self.rot + 1) % 4
        self._orientation_changed()

    def _orientation_changed(self, *_):
        self.flip_h, self.flip_v = self.chk_fh.isChecked(), self.chk_fv.isChecked()
        self.view.clear_rois()
        self.lo = self.hi = None
        self.render()

    def _avg_changed(self, n):
        old = list(self.avg_buf)
        self.avg_buf = deque(old[-n:], maxlen=n)

    def _lock_range(self):
        if self.lo is None or self.chk_diff.isChecked():
            return
        self.spn_lo.setValue(self.lo)
        self.spn_hi.setValue(self.hi)
        self.rb_man.setChecked(True)

    def _diff_toggled(self, on):
        if on and self.ref_base is None:
            self.chk_diff.setChecked(False)
            QMessageBox.information(self, tr("diff_title"), tr("diff_need"))

    def toggle_freeze(self, on):
        self.frozen = on
        if not on:
            self.loaded_name = None
            self.avg_buf.clear()
        self.render()

    def on_status(self, key, ok, idx=-1):
        self.last_status = (key, ok, idx)
        self.lbl_status.setText(("🟢 " if ok else "🔴 ") + tr(key, i=idx))

    def _on_hover(self, h):
        if h is None:
            self.lbl_hover.setText("")
            return
        x, y, v = h
        self.lbl_hover.setText(f"({x},{y})  {fmt_temp(v, self.cmb_unit.currentText(), self.chk_diff.isChecked())}")

    def show_folder(self):
        self._ensure_folder()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder))

    # ================================================================ adquisición y render
    def on_frame(self, raw):
        self.fps_count += 1
        now = time.time()
        if now - self.fps_t0 >= 1.0:
            self.fps = self.fps_count / (now - self.fps_t0)
            self.fps_count, self.fps_t0 = 0, now
        t = raw_to_celsius(raw)
        if self.ref_collect is not None:
            self.ref_collect.append(t)
            self.btn_ref.setText(tr("taking_ref", n=len(self.ref_collect)))
            if len(self.ref_collect) >= 16:
                ref = np.mean(self.ref_collect, axis=0)
                self.ref_collect = None
                self._set_reference(ref, ("ref_captured", {"t": datetime.now().strftime("%H:%M:%S")}))
                self.btn_ref.setText(tr("take_ref"))
        if self.frozen:
            return
        self.avg_buf.append(t)
        self.base = t if len(self.avg_buf) == 1 else np.mean(self.avg_buf, axis=0, dtype=np.float32)
        self.render()
        if self.writer is not None:
            self.writer.write(self._qimage_to_bgr(self.export_image(SMOOTH_SCALE)))

    def render(self, *_):
        if self.base is None:
            return
        eps, trefl = self.spn_eps.value(), self.spn_trefl.value()
        t = correct_emissivity(orient(self.base, self.rot, self.flip_h, self.flip_v), eps, trefl)
        self.temps = t
        diff = (self.chk_diff.isChecked() and self.ref_base is not None
                and self.ref_base.shape == self.base.shape)
        if diff:
            ref = correct_emissivity(orient(self.ref_base, self.rot, self.flip_h, self.flip_v), eps, trefl)
            vals = t - ref
            if self.chk_dauto.isChecked():
                span = max(float(np.percentile(np.abs(vals), 99.7)), 0.5)
                if self._last_diff and self.hi and not self.frozen:
                    span = 0.8 * self.hi + 0.2 * span
                lo, hi = -span, span
            else:
                lo, hi = -self.spn_dspan.value(), self.spn_dspan.value()
            lut = DIFF_LUT
        else:
            vals = t
            if self.rb_auto.isChecked():
                lo, hi = float(vals.min()), float(vals.max())
                if hi - lo < 2.0:
                    c = (hi + lo) / 2
                    lo, hi = c - 1.0, c + 1.0
                if self.lo is not None and not self._last_diff and not self.frozen:
                    lo = 0.7 * self.lo + 0.3 * lo
                    hi = 0.7 * self.hi + 0.3 * hi
            else:
                lo, hi = self.spn_lo.value(), self.spn_hi.value()
                if hi <= lo:
                    hi = lo + 0.1
            lut = self.palettes.get(self.cmb_pal.currentData(), self.palettes[DEFAULT_PALETTE])
        self._last_diff = diff
        self.lo, self.hi, self.cur_lut = lo, hi, lut

        hd = self.cmb_hd.currentIndex()
        if hd > 0:
            disp = upscale(vals, HD_SCALE, hd)
            tt = upscale(t, HD_SCALE, 0)
        elif self.chk_smooth.isChecked():
            disp = upscale(vals, SMOOTH_SCALE)
            tt = upscale(t, SMOOTH_SCALE)
        else:
            disp, tt = vals, t
        rgb = colorize(disp, lo, hi, lut)

        unit = self.cmb_unit.currentText()
        alarm = []
        if self.chk_ahi.isChecked():
            m = tt > self.spn_ahi.value()
            if m.any():
                rgb[m] = ALARM_HI_RGB
                alarm.append(f"{tr('a_high')} {fmt_temp(float(t.max()), unit)}")
        if self.chk_alo.isChecked():
            m = tt < self.spn_alo.value()
            if m.any():
                rgb[m] = ALARM_LO_RGB
                alarm.append(f"{tr('a_low')} {fmt_temp(float(t.min()), unit)}")
        if alarm:
            self.lbl_alarm.setText(tr("alarm") + " " + " · ".join(alarm))
            self.lbl_alarm.show()
            if self.chk_beep.isChecked() and time.time() - self.last_beep > 1.0 and not self.frozen:
                QApplication.beep()
                self.last_beep = time.time()
        else:
            self.lbl_alarm.hide()

        v = self.view
        v.show_max, v.show_min, v.show_center = (self.chk_max.isChecked(), self.chk_min.isChecked(),
                                                 self.chk_ctr.isChecked())
        v.set_frame(rgb, vals, unit, diff)
        self.cbar.set_params(lut, lo, hi, unit, diff)

    def _update_readouts(self):
        v = self.view
        if v.values is None:
            return
        unit, d = v.unit, v.delta
        vals = v.values
        mode = "Δ " if d else ""
        src = (f" · {tr('file')}: {self.loaded_name}" if self.loaded_name
               else (f" · {tr('frozen')}" if self.frozen else ""))
        rec = f" · {tr('recording')}" if self.writer is not None else ""
        self.lbl_stats.setText(
            f"{mode}{tr('max')} {fmt_temp(float(vals.max()), unit, d)}   "
            f"{tr('min')} {fmt_temp(float(vals.min()), unit, d)}   "
            f"{tr('avg_s')} {fmt_temp(float(vals.mean()), unit, d)}   ε {self.spn_eps.value():.2f}   "
            f"{self.fps:.0f} fps{src}{rec}")
        self.table.setRowCount(len(v.rois))
        for r, roi in enumerate(v.rois):
            st = v.roi_stats(roi)
            if roi["type"] == "point":
                cells = [roi["name"], fmt_temp(st["val"], unit, d), "", ""]
            else:
                cells = [roi["name"], fmt_temp(st["max"], unit, d), fmt_temp(st["min"], unit, d),
                         fmt_temp(st["avg"], unit, d)]
            for c, txt in enumerate(cells):
                self.table.setItem(r, c, QTableWidgetItem(txt))

    # ================================================================ exportación
    def export_image(self, scale=4) -> QImage:
        sw, sh = self.view.sensor_size
        iw, ih = sw * scale, sh * scale
        bar_w, info_h = 95, 44
        img = QImage(iw + bar_w, ih + info_h, QImage.Format_RGB888)
        img.fill(QColor(20, 20, 20))
        p = QPainter(img)
        self.view.render_scene(p, QRectF(0, 0, iw, ih), font_pt=max(7.0, 2.3 * scale))
        if self.cur_lut is not None:
            draw_colorbar(p, QRectF(iw, 0, bar_w, ih), self.cur_lut, self.lo, self.hi,
                          self.view.unit, self.view.delta)
        vals, unit, d = self.view.values, self.view.unit, self.view.delta
        f = p.font()
        f.setPointSizeF(9)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(230, 230, 230))
        line1 = (f"UTi260M  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   ε {self.spn_eps.value():.2f}   "
                 f"{tr('t_refl_s')} {self.spn_trefl.value():.1f}°C" + (f"   {tr('diff_mode')}" if d else ""))
        line2 = (f"{tr('max')} {fmt_temp(float(vals.max()), unit, d)}   "
                 f"{tr('min')} {fmt_temp(float(vals.min()), unit, d)}   "
                 f"{tr('avg_s')} {fmt_temp(float(vals.mean()), unit, d)}")
        p.drawText(QRectF(8, ih + 2, iw + bar_w - 16, 20), Qt.AlignLeft | Qt.AlignVCenter, line1)
        p.drawText(QRectF(8, ih + 22, iw + bar_w - 16, 20), Qt.AlignLeft | Qt.AlignVCenter, line2)
        p.end()
        return img

    @staticmethod
    def _qimage_to_bgr(img: QImage) -> np.ndarray:
        img = img.convertToFormat(QImage.Format_RGB888)
        w, h, bpl = img.width(), img.height(), img.bytesPerLine()
        arr = np.frombuffer(img.constBits(), np.uint8, count=bpl * h).reshape(h, bpl)[:, :w * 3]
        return cv2.cvtColor(arr.reshape(h, w, 3), cv2.COLOR_RGB2BGR)

    def _ensure_folder(self):
        os.makedirs(self.folder, exist_ok=True)

    def _meta(self):
        return {
            "date": datetime.now().isoformat(timespec="seconds"),
            "emissivity": self.spn_eps.value(), "t_reflected_c": self.spn_trefl.value(),
            "material": MATERIALS[self.cmb_mat.currentIndex()][0], "rotation": self.rot,
            "mirror_h": self.flip_h, "mirror_v": self.flip_v, "avg_frames": self.spn_avg.value(),
            "differential": bool(self.view.delta),
            "rois": self.view.rois,
        }

    def snapshot(self):
        if self.base is None or self.temps is None:
            return
        self._ensure_folder()
        stem = os.path.join(self.folder, "UTi260M_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        if os.path.exists(stem + ".png"):
            stem += datetime.now().strftime("_%f")[:4]
        self.export_image(4).save(stem + ".png")
        np.savez_compressed(stem + "_data.npz", base=self.base.astype(np.float32),
                            temps_c=self.temps.astype(np.float32),
                            ref=self.ref_base if self.ref_base is not None else np.zeros(0),
                            meta=json.dumps(self._meta(), ensure_ascii=False))
        # CSV: en español ';' y coma decimal (Excel ES); en inglés ',' y punto
        es = i18n.lang() == "es"
        sep = ";" if es else ","
        rows = [sep.join((f"{x:.2f}".replace(".", ",") if es else f"{x:.2f}") for x in row)
                for row in self.temps]
        with open(stem + "_temps.csv", "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows))
        self.statusBar().showMessage(tr("saved", n=os.path.basename(stem)), 5000)

    def toggle_record(self, on):
        if on:
            if self.base is None:
                self.btn_rec.setChecked(False)
                return
            self._ensure_folder()
            self.rec_path = os.path.join(self.folder, "UTi260M_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4")
            frame = self.export_image(SMOOTH_SCALE)
            fps = self.fps if self.fps > 1 else 25
            self.writer = cv2.VideoWriter(self.rec_path, cv2.VideoWriter_fourcc(*"mp4v"), round(fps),
                                          (frame.width(), frame.height()))
            if not self.writer.isOpened():
                self.writer = None
                self.btn_rec.setChecked(False)
                QMessageBox.warning(self, tr("video"), tr("video_fail"))
                return
            self.btn_rec.setText(tr("rec_stop"))
            self.btn_rec.setStyleSheet("background: #c00; color: white")
        else:
            if self.writer is not None:
                self.writer.release()
                self.writer = None
                self.statusBar().showMessage(tr("video_saved", n=os.path.basename(self.rec_path)), 5000)
            self.btn_rec.setText(tr("rec"))
            self.btn_rec.setStyleSheet("")

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr("dlg_folder"), self.folder)
        if d:
            self.folder = d
            self.lbl_folder.setText(d)

    def open_capture(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dlg_open"), self.folder, tr("open_filter"))
        if not path:
            return
        try:
            z = np.load(path, allow_pickle=False)
            base = z["base"].astype(np.float32)
            meta = json.loads(str(z["meta"]))
        except Exception as e:
            QMessageBox.warning(self, tr("dlg_open"), tr("read_fail", e=e))
            return
        m = lambda new, old, d: meta.get(new, meta.get(old, d))  # compatible con capturas antiguas
        self.btn_freeze.setChecked(True)
        self.base = base
        self.loaded_name = os.path.basename(path)
        self.rot = int(m("rotation", "rotacion", 0))
        for chk, new, old in ((self.chk_fh, "mirror_h", "espejo_h"), (self.chk_fv, "mirror_v", "espejo_v")):
            chk.blockSignals(True)
            chk.setChecked(bool(m(new, old, False)))
            chk.blockSignals(False)
        self.flip_h, self.flip_v = self.chk_fh.isChecked(), self.chk_fv.isChecked()
        self.spn_eps.setValue(float(m("emissivity", "emisividad", self.spn_eps.value())))
        self.spn_trefl.setValue(float(m("t_reflected_c", "t_reflejada_c", self.spn_trefl.value())))
        self.view.rois = [r for r in m("rois", "mediciones", []) if isinstance(r, dict)]
        self.lo = self.hi = None
        self.render()

    # ================================================================ referencia
    def take_reference(self):
        if self.frozen and self.base is not None:
            self._set_reference(self.base.copy(), ("ref_frozen", {}))
        else:
            self.ref_collect = []

    def _set_reference(self, ref, desc):
        self.ref_base = ref.astype(np.float32)
        self.ref_desc = desc
        self.lbl_ref.setText(tr("ref_is", d=tr(desc[0], **desc[1])))
        self.render()

    def save_reference(self):
        if self.ref_base is None:
            QMessageBox.information(self, tr("ref_title"), tr("ref_none"))
            return
        self._ensure_folder()
        path, _ = QFileDialog.getSaveFileName(self, tr("save_ref"),
                                              os.path.join(self.folder, "reference_pcb.npz"), tr("ref_filter"))
        if path:
            np.savez_compressed(path, ref=self.ref_base)

    def load_reference(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("load_ref"), self.folder, tr("ref_filter"))
        if not path:
            return
        try:
            z = np.load(path, allow_pickle=False)
            ref = z["ref"] if "ref" in z and z["ref"].size else z["base"]
        except Exception as e:
            QMessageBox.warning(self, tr("ref_title"), tr("read_fail", e=e))
            return
        self._set_reference(ref, ("file_ref", {"n": os.path.basename(path)}))

    # ================================================================ cierre
    def closeEvent(self, ev):
        if self.writer is not None:
            self.toggle_record(False)
        self._save_settings()
        self.cam.stop()
        super().closeEvent(ev)

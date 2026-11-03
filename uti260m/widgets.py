"""Widgets de visualización: imagen térmica con mediciones y barra de color."""
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget

from .i18n import tr
from .processing import fmt_temp

COL_MAX = QColor(255, 60, 60)
COL_MIN = QColor(60, 170, 255)
COL_CENTER = QColor(255, 255, 255)
COL_ROI = QColor(255, 255, 0)


def np_to_qimage(rgb: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(rgb)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def draw_label(p: QPainter, x, y, text, color, bounds: QRectF = None):
    fm = p.fontMetrics()
    w = fm.horizontalAdvance(text) + 8
    h = fm.height() + 2
    r = QRectF(x + 8, y - h - 4, w, h)
    if bounds is not None:  # mantener dentro de la imagen
        if r.right() > bounds.right():
            r.moveRight(x - 8)
        if r.top() < bounds.top():
            r.moveTop(y + 6)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 160))
    p.drawRoundedRect(r, 3, 3)
    p.setPen(color)
    p.drawText(r, Qt.AlignCenter, text)


def draw_marker(p: QPainter, x, y, color, kind):
    p.setBrush(Qt.NoBrush)
    s = 7
    if kind == "max":
        poly = QPolygonF([QPointF(x, y - s), QPointF(x - s, y + s * 0.7), QPointF(x + s, y + s * 0.7)])
    elif kind == "min":
        poly = QPolygonF([QPointF(x, y + s), QPointF(x - s, y - s * 0.7), QPointF(x + s, y - s * 0.7)])
    else:
        poly = None
    for width, col in ((3, QColor(0, 0, 0, 200)), (1.5, color)):
        p.setPen(QPen(col, width))
        if poly is not None:
            p.drawPolygon(poly)
        else:
            p.drawLine(QPointF(x - 9, y), QPointF(x - 3, y))
            p.drawLine(QPointF(x + 3, y), QPointF(x + 9, y))
            p.drawLine(QPointF(x, y - 9), QPointF(x, y - 3))
            p.drawLine(QPointF(x, y + 3), QPointF(x, y + 9))


def draw_colorbar(p: QPainter, rect: QRectF, lut, lo, hi, unit, delta=False):
    bar = QRectF(rect.x() + 4, rect.y() + 10, 16, rect.height() - 20)
    grad = np.repeat(lut[::-1][:, None, :], 4, axis=1)
    p.drawImage(bar, np_to_qimage(grad))
    p.setPen(QColor(200, 200, 200))
    p.setBrush(Qt.NoBrush)
    p.drawRect(bar)
    f = p.font()
    f.setPointSizeF(8.5)
    p.setFont(f)
    n = 6
    for i in range(n):
        frac = i / (n - 1)
        v = hi - (hi - lo) * frac
        y = bar.top() + bar.height() * frac
        p.drawLine(QPointF(bar.right(), y), QPointF(bar.right() + 4, y))
        p.drawText(QRectF(bar.right() + 6, y - 8, rect.width() - 28, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, fmt_temp(v, unit, delta))


class ThermalView(QWidget):
    """Muestra la imagen térmica; clic = punto, arrastrar = rectángulo, clic derecho = borrar."""
    hover = Signal(object)          # (x, y, valor) o None
    rois_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.qimg = None
        self.values = None          # matriz mostrada (temperatura o delta), °C
        self.unit = "°C"
        self.delta = False
        self.show_max = self.show_min = self.show_center = True
        self.rois = []
        self._drag_start = None
        self._drag_now = None
        self._next_id = {"point": 1, "rect": 1}

    # ------------------------------------------------------------ datos
    def set_frame(self, rgb, values, unit, delta):
        self.qimg = np_to_qimage(rgb)
        self.values = values
        self.unit = unit
        self.delta = delta
        self.update()

    @property
    def sensor_size(self):
        if self.values is None:
            return 256, 192
        return self.values.shape[1], self.values.shape[0]

    def clear_rois(self):
        self.rois.clear()
        self._next_id = {"point": 1, "rect": 1}
        self.rois_changed.emit()
        self.update()

    def roi_stats(self, roi):
        v = self.values
        if v is None:
            return None
        if roi["type"] == "point":
            return {"val": float(v[roi["y"], roi["x"]])}
        sub = v[roi["y0"]:roi["y1"] + 1, roi["x0"]:roi["x1"] + 1]
        iy, ix = np.unravel_index(np.argmax(sub), sub.shape)
        jy, jx = np.unravel_index(np.argmin(sub), sub.shape)
        return {"max": float(sub[iy, ix]), "min": float(sub[jy, jx]), "avg": float(sub.mean()),
                "max_xy": (roi["x0"] + ix, roi["y0"] + iy), "min_xy": (roi["x0"] + jx, roi["y0"] + jy)}

    # ------------------------------------------------------------ geometría
    def image_rect(self, w, h) -> QRectF:
        sw, sh = self.sensor_size
        scale = min(w / sw, h / sh)
        dw, dh = sw * scale, sh * scale
        return QRectF((w - dw) / 2, (h - dh) / 2, dw, dh)

    def _to_sensor(self, pos):
        r = self.image_rect(self.width(), self.height())
        sw, sh = self.sensor_size
        x = int((pos.x() - r.x()) / r.width() * sw)
        y = int((pos.y() - r.y()) / r.height() * sh)
        if 0 <= x < sw and 0 <= y < sh:
            return x, y
        return None

    def _clamp(self, pos):
        r = self.image_rect(self.width(), self.height())
        sw, sh = self.sensor_size
        x = int((pos.x() - r.x()) / r.width() * sw)
        y = int((pos.y() - r.y()) / r.height() * sh)
        return min(max(x, 0), sw - 1), min(max(y, 0), sh - 1)

    # ------------------------------------------------------------ dibujo
    def render_scene(self, p: QPainter, rect: QRectF, font_pt=9.0):
        if self.qimg is None:
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawImage(rect, self.qimg)
        if self.values is None:
            return
        f = QFont(p.font())
        f.setPointSizeF(font_pt)
        f.setBold(True)
        p.setFont(f)
        sw, sh = self.sensor_size
        sx, sy = rect.width() / sw, rect.height() / sh

        def to_disp(x, y):
            return rect.x() + (x + 0.5) * sx, rect.y() + (y + 0.5) * sy

        v = self.values
        u, d = self.unit, self.delta
        for roi in self.rois:
            st = self.roi_stats(roi)
            if roi["type"] == "point":
                x, y = to_disp(roi["x"], roi["y"])
                draw_marker(p, x, y, COL_ROI, "center")
                draw_label(p, x, y, f"{roi['name']} {fmt_temp(st['val'], u, d)}", COL_ROI, rect)
            else:
                x0, y0 = rect.x() + roi["x0"] * sx, rect.y() + roi["y0"] * sy
                x1, y1 = rect.x() + (roi["x1"] + 1) * sx, rect.y() + (roi["y1"] + 1) * sy
                for width, col in ((3, QColor(0, 0, 0, 180)), (1.5, COL_ROI)):
                    p.setPen(QPen(col, width))
                    p.setBrush(Qt.NoBrush)
                    p.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)))
                mx, my = to_disp(*st["max_xy"])
                draw_marker(p, mx, my, COL_MAX, "max")
                draw_label(p, x0 - 8, y0 + 2,
                           f"{roi['name']} {tr('roi_max')} {fmt_temp(st['max'], u, d)} {tr('roi_avg')} {fmt_temp(st['avg'], u, d)}",
                           COL_ROI, rect)
        if self.show_center:
            cx, cy = sw // 2, sh // 2
            x, y = to_disp(cx, cy)
            draw_marker(p, x, y, COL_CENTER, "center")
            draw_label(p, x, y, fmt_temp(float(v[cy, cx]), u, d), COL_CENTER, rect)
        if self.show_max:
            iy, ix = np.unravel_index(np.argmax(v), v.shape)
            x, y = to_disp(ix, iy)
            draw_marker(p, x, y, COL_MAX, "max")
            draw_label(p, x, y, fmt_temp(float(v[iy, ix]), u, d), COL_MAX, rect)
        if self.show_min:
            iy, ix = np.unravel_index(np.argmin(v), v.shape)
            x, y = to_disp(ix, iy)
            draw_marker(p, x, y, COL_MIN, "min")
            draw_label(p, x, y, fmt_temp(float(v[iy, ix]), u, d), COL_MIN, rect)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 20, 20))
        if self.qimg is None:
            p.setPen(QColor(180, 180, 180))
            p.drawText(self.rect(), Qt.AlignCenter, tr("waiting"))
            return
        r = self.image_rect(self.width(), self.height())
        self.render_scene(p, r)
        if self._drag_start and self._drag_now:
            sw, sh = self.sensor_size
            sx, sy = r.width() / sw, r.height() / sh
            (ax, ay), (bx, by) = self._drag_start, self._drag_now
            p.setPen(QPen(COL_ROI, 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(r.x() + min(ax, bx) * sx, r.y() + min(ay, by) * sy,
                              (abs(bx - ax) + 1) * sx, (abs(by - ay) + 1) * sy))

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, ev):
        pos = self._to_sensor(ev.position())
        if pos is None:
            return
        if ev.button() == Qt.LeftButton:
            self._drag_start = self._drag_now = pos
        elif ev.button() == Qt.RightButton:
            self._remove_near(pos)

    def mouseMoveEvent(self, ev):
        if self._drag_start:
            self._drag_now = self._clamp(ev.position())
            self.update()
        pos = self._to_sensor(ev.position())
        if pos is not None and self.values is not None:
            self.hover.emit((pos[0], pos[1], float(self.values[pos[1], pos[0]])))
        else:
            self.hover.emit(None)

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or not self._drag_start:
            return
        (ax, ay), (bx, by) = self._drag_start, self._clamp(ev.position())
        self._drag_start = self._drag_now = None
        if abs(bx - ax) < 3 and abs(by - ay) < 3:
            n = self._next_id["point"]
            self._next_id["point"] += 1
            self.rois.append({"type": "point", "x": ax, "y": ay, "name": f"P{n}"})
        else:
            n = self._next_id["rect"]
            self._next_id["rect"] += 1
            self.rois.append({"type": "rect", "x0": min(ax, bx), "y0": min(ay, by),
                              "x1": max(ax, bx), "y1": max(ay, by), "name": f"R{n}"})
        self.rois_changed.emit()
        self.update()

    def leaveEvent(self, ev):
        self.hover.emit(None)

    def _remove_near(self, pos):
        x, y = pos
        best, best_d = None, 1e9
        for i, roi in enumerate(self.rois):
            if roi["type"] == "point":
                dd = (roi["x"] - x) ** 2 + (roi["y"] - y) ** 2
                if dd >= 64:
                    continue
            else:
                if not (roi["x0"] - 2 <= x <= roi["x1"] + 2 and roi["y0"] - 2 <= y <= roi["y1"] + 2):
                    continue
                dd = (roi["x1"] - roi["x0"]) * (roi["y1"] - roi["y0"])  # el más pequeño primero
            if dd < best_d:
                best, best_d = i, dd
        if best is not None:
            self.rois.pop(best)
            self.rois_changed.emit()
            self.update()


class ColorBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(82)
        self.lut = None
        self.lo, self.hi, self.unit, self.delta = 0, 1, "°C", False

    def set_params(self, lut, lo, hi, unit, delta):
        self.lut, self.lo, self.hi, self.unit, self.delta = lut, lo, hi, unit, delta
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 20, 20))
        if self.lut is not None:
            draw_colorbar(p, QRectF(self.rect()), self.lut, self.lo, self.hi, self.unit, self.delta)


class Section(QWidget):
    """Sección desplegable: encabezado con flecha + contenido."""
    toggled = Signal(bool)

    def __init__(self, title="", expanded=False, parent=None):
        super().__init__(parent)
        self.btn = QToolButton()
        self.btn.setText(title)
        self.btn.setCheckable(True)
        self.btn.setChecked(expanded)
        self.btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn.setStyleSheet("QToolButton { border: none; font-weight: bold; padding: 5px 2px;"
                               " text-align: left; background: rgba(255,255,255,12); border-radius: 3px; }"
                               "QToolButton:hover { background: rgba(255,255,255,28); }")
        self.btn.toggled.connect(self._toggle)
        self.body = QWidget()
        self.body.setVisible(expanded)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 2)
        lay.setSpacing(2)
        lay.addWidget(self.btn)
        lay.addWidget(self.body)

    def setTitle(self, t):
        self.btn.setText(t)

    def isExpanded(self):
        return self.btn.isChecked()

    def setExpanded(self, on):
        self.btn.setChecked(on)

    def _toggle(self, on):
        self.btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)
        self.toggled.emit(on)
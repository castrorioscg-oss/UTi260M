"""Adquisición de cuadros desde la UTi260M (UVC 256x384 YUYV) en un hilo aparte."""
import os
import time

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from .processing import FRAME_BYTES, SENSOR_H, SENSOR_W, KELVIN, parse_frame


def _try_open(idx):
    cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    for _ in range(5):
        ok, f = cap.read()
        if ok and f is not None and f.size == FRAME_BYTES:
            return cap
    cap.release()
    return None


class CameraThread(QThread):
    frame = Signal(object)          # np.ndarray uint16 (192x256), datos crudos
    status = Signal(str, bool, int)  # clave i18n, conectada, índice
    found_index = Signal(int)

    def __init__(self, preferred_index=None, parent=None):
        super().__init__(parent)
        self.preferred = preferred_index
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(3000)

    def _open(self):
        order = ([self.preferred] if self.preferred is not None else []) + \
                [i for i in range(8) if i != self.preferred]
        for idx in order:
            if self._stop:
                return None, None
            cap = _try_open(idx)
            if cap is not None:
                return cap, idx
        return None, None

    def run(self):
        while not self._stop:
            self.status.emit("st_search", False, -1)
            cap, idx = self._open()
            if cap is None:
                self.status.emit("st_notfound", False, -1)
                for _ in range(20):
                    if self._stop:
                        return
                    self.msleep(100)
                continue
            self.preferred = idx
            self.found_index.emit(idx)
            self.status.emit("st_conn", True, idx)
            fails = 0
            while not self._stop:
                ok, f = cap.read()
                if not ok or f is None or f.size != FRAME_BYTES:
                    fails += 1
                    if fails > 30:
                        break
                    self.msleep(30)
                    continue
                fails = 0
                self.frame.emit(parse_frame(f))
            cap.release()
            if not self._stop:
                self.status.emit("st_lost", False, -1)
                self.msleep(500)


class DemoThread(QThread):
    """Genera una PCB sintética para probar la interfaz sin cámara."""
    frame = Signal(object)
    status = Signal(str, bool, int)
    found_index = Signal(int)

    def __init__(self, *a, **k):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(2000)

    def run(self):
        self.status.emit("st_demo", True, -1)
        yy, xx = np.mgrid[0:SENSOR_H, 0:SENSOR_W].astype(np.float32)
        base = 24 + 2 * np.exp(-((xx - 128) ** 2 + (yy - 96) ** 2) / 8000)
        spots = [(60, 50, 40, 9), (180, 70, 18, 6), (120, 150, 55, 4), (210, 160, 8, 12)]
        t0 = time.time()
        while not self._stop:
            t = time.time() - t0
            img = base.copy()
            for i, (x, y, amp, r) in enumerate(spots):
                a = amp * (0.85 + 0.15 * np.sin(t * (0.5 + i * 0.3)))
                img += a * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * r * r))
            img += np.random.normal(0, 0.08, img.shape)
            self.frame.emit(((img + KELVIN) * 64).astype(np.uint16))
            self.msleep(40)

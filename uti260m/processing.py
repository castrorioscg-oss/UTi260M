"""Procesamiento de datos térmicos: decodificación, emisividad, paletas, estadísticas."""
import numpy as np
import cv2

KELVIN = 273.15
SENSOR_W, SENSOR_H = 256, 192
FRAME_BYTES = SENSOR_W * SENSOR_H * 2 * 2  # imagen (YUYV) + datos crudos, 16 bits

# Emisividad que asume la cámara al reportar los datos crudos.
# El módulo entrega la temperatura con su emisividad interna (por defecto ~1.0).
# Si notas un desvío sistemático contra un termómetro de referencia, ajusta este valor.
EPS_DEVICE = 1.0


def parse_frame(buf: np.ndarray) -> np.ndarray:
    """Recibe el buffer YUYV 256x384 y devuelve los datos crudos (192x256 uint16)."""
    f = buf.reshape(SENSOR_H * 2, SENSOR_W, 2)
    return np.ascontiguousarray(f[SENSOR_H:]).view("<u2").reshape(SENSOR_H, SENSOR_W)


def raw_to_celsius(raw: np.ndarray) -> np.ndarray:
    return raw.astype(np.float32) / 64.0 - KELVIN


def correct_emissivity(t_c: np.ndarray, eps: float, t_refl_c: float) -> np.ndarray:
    """Corrige por emisividad y temperatura reflejada (aprox. Stefan-Boltzmann)."""
    if abs(eps - EPS_DEVICE) < 1e-4:
        return t_c
    tr4 = (t_refl_c + KELVIN) ** 4
    w = EPS_DEVICE * (t_c + KELVIN) ** 4 + (1.0 - EPS_DEVICE) * tr4
    to4 = (w - (1.0 - eps) * tr4) / eps
    return (np.power(np.clip(to4, 1.0, None), 0.25) - KELVIN).astype(np.float32)


def orient(a: np.ndarray, rot: int, flip_h: bool, flip_v: bool) -> np.ndarray:
    if rot:
        a = np.rot90(a, -rot)  # rot = número de giros de 90° en sentido horario
    if flip_h:
        a = a[:, ::-1]
    if flip_v:
        a = a[::-1, :]
    return np.ascontiguousarray(a)


# ---------------------------------------------------------------- paletas
def _gradient(stops):
    """stops: lista de (posición 0..1, (r,g,b)) -> LUT 256x3 uint8 RGB."""
    x = np.linspace(0, 1, 256)
    pos = [s[0] for s in stops]
    lut = np.zeros((256, 3), np.uint8)
    for c in range(3):
        lut[:, c] = np.interp(x, pos, [s[1][c] for s in stops])
    return lut


def _cv_lut(cmap):
    g = np.arange(256, dtype=np.uint8).reshape(256, 1)
    return cv2.applyColorMap(g, cmap).reshape(256, 3)[:, ::-1].copy()


def build_palettes():
    """Devuelve {id: LUT}; el nombre visible se traduce con i18n ('pal_<id>')."""
    gray = np.repeat(np.arange(256, dtype=np.uint8)[:, None], 3, axis=1)
    return {
        "lava": _cv_lut(cv2.COLORMAP_INFERNO),
        "iron": _gradient([
            (0.0, (0, 0, 0)), (0.15, (30, 0, 110)), (0.35, (140, 0, 150)),
            (0.55, (225, 50, 30)), (0.75, (255, 150, 0)), (0.9, (255, 225, 60)),
            (1.0, (255, 255, 255))]),
        "rainbow": _cv_lut(cv2.COLORMAP_JET),
        "rainbow_hc": _cv_lut(cv2.COLORMAP_TURBO),
        "white_hot": gray,
        "black_hot": gray[::-1].copy(),
        "magma": _cv_lut(cv2.COLORMAP_MAGMA),
        "red_hot": _gradient([(0.0, (0, 0, 0)), (0.7, (110, 110, 110)),
                              (0.85, (255, 80, 0)), (1.0, (255, 0, 0))]),
    }


DIFF_LUT = _gradient([(0.0, (0, 40, 200)), (0.25, (60, 140, 255)), (0.5, (255, 255, 255)),
                      (0.75, (255, 140, 40)), (1.0, (200, 0, 0))])


def colorize(data: np.ndarray, lo: float, hi: float, lut: np.ndarray) -> np.ndarray:
    span = max(hi - lo, 1e-3)
    a = 255.0 / span
    # convertScaleAbs satura a 0..255; restar lo antes evita valores negativos reflejados
    idx = cv2.convertScaleAbs(np.maximum(data, lo), alpha=a, beta=-lo * a)
    return cv2.LUT(cv2.merge([idx, idx, idx]), lut.reshape(256, 1, 3))


# ---------------------------------------------------------------- materiales
MATERIALS = [  # (clave i18n, emisividad)
    ("mat_custom", None),
    ("mat_mask", 0.92),
    ("mat_fr4", 0.90),
    ("mat_ic", 0.93),
    ("mat_kapton", 0.95),
    ("mat_paint", 0.97),
    ("mat_ceramic", 0.90),
    ("mat_silicone", 0.90),
    ("mat_anod", 0.80),
    ("mat_cu_ox", 0.65),
    ("mat_al", 0.10),
    ("mat_solder", 0.08),
    ("mat_cu_pol", 0.05),
    ("mat_skin", 0.98),
    ("mat_bb", 1.00),
]


# ---------------------------------------------------------------- HD (mejora de imagen)
HD_SCALE = 4
_HD_PARAMS = {  # nivel: (diámetro bilateral, sigma de color en °C, ganancia de detalle)
    1: (5, 0.15, 0.8),
    2: (7, 0.20, 1.6),
    3: (9, 0.25, 2.6),
}


def upscale(vals: np.ndarray, scale: int, hd_level: int = 0) -> np.ndarray:
    """Amplía la matriz para visualización.

    hd_level 0: interpolación bicúbica.
    hd_level 1..3: filtro bilateral (quita ruido sin borrar bordes) + Lanczos +
    realce de detalle tipo DDE (capa base/detalle). Solo para mostrar: no altera las mediciones.
    """
    h, w = vals.shape
    size = (w * scale, h * scale)
    if hd_level <= 0:
        return cv2.resize(vals, size, interpolation=cv2.INTER_CUBIC)
    d, sig_c, gain = _HD_PARAMS[min(hd_level, 3)]
    # el ruido del sensor es absoluto (~0.1 °C), por eso sigma_color no depende del rango
    den = cv2.bilateralFilter(vals.astype(np.float32), d, sig_c, d / 2.5)
    big = cv2.resize(den, size, interpolation=cv2.INTER_LANCZOS4)
    base = cv2.GaussianBlur(big, (0, 0), scale)
    return big + gain * (big - base)


def c_to_unit(t, unit, delta=False):
    if unit == "°F":
        return t * 9.0 / 5.0 + (0 if delta else 32.0)
    if unit == "K" and not delta:
        return t + KELVIN
    return t


def fmt_temp(t, unit, delta=False):
    v = c_to_unit(t, unit, delta)
    return f"{'+' if delta and v > 0 else ''}{v:.1f}{'K' if unit == 'K' else unit}"

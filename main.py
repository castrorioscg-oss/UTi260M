"""Visor térmico para UNI-T UTi260M.

Uso:
    python main.py            # cámara real (detección automática)
    python main.py --demo     # datos sintéticos, sin cámara
    python main.py --index 1  # forzar índice de dispositivo de video
"""
import argparse
import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from uti260m.app import MainWindow


def dark_palette():
    p = QPalette()
    c = {
        QPalette.Window: (45, 45, 48), QPalette.WindowText: (230, 230, 230),
        QPalette.Base: (30, 30, 32), QPalette.AlternateBase: (45, 45, 48),
        QPalette.Text: (230, 230, 230), QPalette.Button: (60, 60, 64),
        QPalette.ButtonText: (230, 230, 230), QPalette.Highlight: (0, 120, 215),
        QPalette.HighlightedText: (255, 255, 255), QPalette.ToolTipBase: (60, 60, 64),
        QPalette.ToolTipText: (230, 230, 230), QPalette.PlaceholderText: (140, 140, 140),
    }
    for role, rgb in c.items():
        p.setColor(role, QColor(*rgb))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--index", type=int, default=None)
    args = ap.parse_args()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    w =MainWindow(demo=args.demo, index=args.index)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

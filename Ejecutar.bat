@echo off
cd /d "%~dp0"
python -c "import cv2, PySide6, numpy" 2>nul || python -m pip install -r requirements.txt
start "" pythonw main.py %*

@echo off
rem Genera dist\UTi260M\UTi260M.exe (carpeta portable, no requiere Python)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name UTi260M main.py
echo.
echo Listo: dist\UTi260M\UTi260M.exe
pause

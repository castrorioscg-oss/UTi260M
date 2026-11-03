@echo off
rem Genera dist\UTi260M\UTi260M.exe (carpeta portable, no requiere Python)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name UTi260M ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy ^
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQuickWidgets ^
  --exclude-module PySide6.QtPdf --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtOpenGL ^
  --exclude-module PySide6.QtOpenGLWidgets --exclude-module PySide6.QtSvg --exclude-module PySide6.QtWebEngineCore ^
  main.py
rem Quitar DLLs de Qt que no se usan (reduce ~50 MB)
for %%F in (opengl32sw.dll Qt6Quick.dll Qt6Qml.dll Qt6QmlMeta.dll Qt6QmlModels.dll Qt6QmlWorkerScript.dll Qt6Pdf.dll Qt6OpenGL.dll Qt6Network.dll Qt6VirtualKeyboard.dll) do (
  for /r "dist\UTi260M\_internal" %%G in (%%F) do if exist "%%G" del "%%G"
)
echo.
echo Listo: dist\UTi260M\UTi260M.exe
pause

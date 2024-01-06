@echo off
SETLOCAL EnableDelayedExpansion

set "REUSE_VENV=%~1"
if "%REUSE_VENV%"=="" set "REUSE_VENV=0"

set "GUI_DIR=%~dp0"
set "REPO_DIR=%GUI_DIR%.."
set "SRC_DIR=%REPO_DIR%\src"
set "PARSAGON_DIR=%SRC_DIR%\parsagon"
set "GRAPHICS_DIR=%PARSAGON_DIR%\graphics"

if not "%VIRTUAL_ENV%"=="" (
    echo A virtual environment is currently active.
    echo Please deactivate the virtual environment before running this script.
    exit /b 1
)

cd /d "%SRC_DIR%"

if exist *.spec del *.spec
if exist dist rd /s /q dist
if exist build rd /s /q build

if "%REUSE_VENV%"=="0" (
    if exist venv rd /s /q venv
    python -m venv venv
)

call venv\Scripts\activate.bat

if "%REUSE_VENV%"=="0" (
    pip install ..
    pip uninstall -y parsagon
    pip install PyQt6==6.6.1
    pip install pyinstaller==6.3.0
)

set "PYINSTALLER_CMD=python -m PyInstaller --name Parsagon --icon "%GUI_DIR%\windows.ico" --onefile --windowed --add-data "%PARSAGON_DIR%\highlights.js;.""

for /r "%GRAPHICS_DIR%" %%f in (*.*) do (
    set "PYINSTALLER_CMD=!PYINSTALLER_CMD! --add-data "%%f;graphics""
)

echo !PYINSTALLER_CMD!
!PYINSTALLER_CMD! --clean .\parsagon\gui_entry.py

ENDLOCAL

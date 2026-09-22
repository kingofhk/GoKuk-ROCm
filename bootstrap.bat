@echo off
REM GoKuk-ROCm bootstrap script - run once on a fresh Windows clone.
REM Sets up PySide6, verifies the fork's Phase 4 GPU detection,
REM then opens Gokuk Setup.

echo === GoKuk-ROCm bootstrap ===
echo.

cd /d D:\GoKuk

echo === [1/4] Installing runtime requirements (PySide6, requests) ===
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo === [2/4] Verifying PySide6 import ===
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
if errorlevel 1 goto :fail

echo.
echo === [3/4] Phase 4 GPU detection smoke test ===
python -c "import sys; sys.path.insert(0, '.'); from app.gpu import detect; g = detect(); print('detect():', g)"
if errorlevel 1 goto :fail

echo.
echo === [4/4] Launching Gokuk Setup ===
python GokukSetup.py

goto :end

:fail
echo.
echo *** FAILED - check messages above ***
echo.
pause

:end
echo.
echo Done.
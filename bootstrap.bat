@echo off
REM GoKuk-ROCm bootstrap script - run once on a fresh Windows clone.
REM Sets up PySide6, verifies the fork's Phase 4 GPU detection,
REM then opens Gokuk Setup.
REM
REM Default: uses Python's embedded distribution at C:\Python314e\
REM (downloads + extracts python-3.14.7-embed-amd64.zip if absent).
REM This avoids the standard MSI installer, which fails on
REM Adrenalin-only Windows boxes that already have the PythonManager
REM stub installed by winget (Windows Installer error 0x80070070).
REM Override with GOKUK_PYTHON=path\to\python.exe to use a system
REM install instead.

echo === GoKuk-ROCm bootstrap ===
echo.

setlocal
set "PYTHON=%GOKUK_PYTHON%"
if "%PYTHON%"=="" (
    set "PYTHON=C:\Python314e\python.exe"
)
set "EMBED_ZIP=%TEMP%\python-3.14.7-embed-amd64.zip"
set "EMBED_URL=https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip"
set "EMBED_DIR=C:\Python314e"

REM ---- [0/4] Make sure embedded Python exists ----
if not exist "%PYTHON%" (
    echo Embedded Python not found at %PYTHON%.
    if not exist "%EMBED_DIR%" mkdir "%EMBED_DIR%"
    echo Downloading %EMBED_URL% ...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%EMBED_URL%' -OutFile '%EMBED_ZIP%'"
    if errorlevel 1 goto :fail
    echo Extracting ...
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%EMBED_ZIP%' -DestinationPath '%EMBED_DIR%' -Force"
    if errorlevel 1 goto :fail
    REM Uncomment "import site" so pip can install
    powershell -NoProfile -Command "(Get-Content '%EMBED_DIR%\python314._pth') -replace '^#import site$', 'import site' | Set-Content '%EMBED_DIR%\python314._pth'"
    REM Bootstrap pip
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%EMBED_DIR%\get-pip.py'"
    "%PYTHON%" "%EMBED_DIR%\get-pip.py" --no-warn-script-location
    del "%EMBED_DIR%\get-pip.py"
)

echo.
echo === [1/4] Installing runtime requirements (PySide6, requests) ===
"%PYTHON%" -m pip install --quiet --upgrade pip
if errorlevel 1 goto :fail
"%PYTHON%" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo === [2/4] Verifying PySide6 import ===
"%PYTHON%" -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
if errorlevel 1 goto :fail

echo.
echo === [3/4] Phase 4 GPU detection smoke test ===
cd /d D:\GoKuk
"%PYTHON%" -c "import sys; sys.path.insert(0, '.'); from app.gpu import detect; g = detect(); print('detect():', g)"
if errorlevel 1 goto :fail

echo.
echo === [4/4] Launching Gokuk Setup ===
"%PYTHON%" GokukSetup.py

goto :end

:fail
echo.
echo *** FAILED - check messages above ***
echo.
pause

:end
echo.
echo Done.

endlocal
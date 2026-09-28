@echo off
REM ===================================================================
REM  GokukSetup-ROCm launcher (created 2026-09-28 by yaubiu via A2A Phase 7)
REM  Uses the dedicated gui venv - no py launcher, no PATH python needed.
REM ===================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Gokuk Setup

set "GUIPY=%~dp0runtime\gui\Scripts\pythonw.exe"
if not exist "%GUIPY%" set "GUIPY=%~dp0runtime\gui\Scripts\python.exe"
if not exist "%GUIPY%" (
    echo GUI runtime missing - run bootstrap first.
    pause
    exit /b 1
)

start "Gokuk Setup" "%GUIPY%" "%~dp0GokukSetup.py"

@echo off
title SubNova Studio - AI Subtitle Translator & Improver (Hatim Alharbi)
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Encountered error running SubNova Studio.
    pause
)

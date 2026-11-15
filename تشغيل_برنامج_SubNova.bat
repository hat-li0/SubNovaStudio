@echo off
title تشغيل SubNova Studio
cd /d "%~dp0pc_version"

if exist "dist\SubNovaStudio\SubNovaStudio.exe" (
    start "" "dist\SubNovaStudio\SubNovaStudio.exe"
    exit /b 0
)

if exist "dist\SubNovaStudio_Standalone.exe" (
    start "" "dist\SubNovaStudio_Standalone.exe"
    exit /b 0
)

if exist "dist\SubNovaStudio.exe" (
    start "" "dist\SubNovaStudio.exe"
    exit /b 0
)

echo Starting via Python environment...
start "" pythonw main.py
exit /b 0

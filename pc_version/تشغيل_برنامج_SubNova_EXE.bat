@echo off
chcp 65001 >nul
title SubNova Studio — استوديو سوب نوفا
cd /d "%~dp0"

:: تشغيل النسخة المستقرة فائقة السرعة
if exist "%~dp0dist\SubNovaStudio\SubNovaStudio.exe" (
    cd /d "%~dp0dist\SubNovaStudio"
    start "" "SubNovaStudio.exe"
    exit /b 0
)

if exist "%~dp0dist\SubNovaStudio_Standalone.exe" (
    cd /d "%~dp0dist"
    start "" "%~dp0dist\SubNovaStudio_Standalone.exe"
    exit /b 0
)

if exist "%~dp0dist\SubNovaStudio.exe" (
    cd /d "%~dp0dist"
    start "" "%~dp0dist\SubNovaStudio.exe"
    exit /b 0
)

python main.py
exit /b 0

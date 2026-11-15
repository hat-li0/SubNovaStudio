@echo off
chcp 65001 >nul
title تشغيل SubNova Studio
cd /d "%~dp0"

:: 1. تشغيل نسخة المجلد الكاملة السريعة والمستقرة (Onedir)
if exist "%~dp0dist\SubNovaStudio\SubNovaStudio.exe" (
    cd /d "%~dp0dist\SubNovaStudio"
    start "" "SubNovaStudio.exe"
    exit /b 0
)

:: 2. تشغيل النسخة المستقلة المحمولة (Standalone Onefile)
if exist "%~dp0dist\SubNovaStudio_Standalone.exe" (
    start "" "%~dp0dist\SubNovaStudio_Standalone.exe"
    exit /b 0
)

if exist "%~dp0dist\SubNovaStudio.exe" (
    start "" "%~dp0dist\SubNovaStudio.exe"
    exit /b 0
)

:: 3. تشغيل عبر بيئة بايثون المباشرة
echo جاري تشغيل التطبيق عبر بيئة بايثون...
start "" pythonw main.py
exit /b 0

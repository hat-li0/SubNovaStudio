@echo off
title SubNova Studio - Build Standalone EXE
cd /d "%~dp0"
echo ===================================================
echo     Building SubNova Studio (Onedir + Standalone)...
echo ===================================================
echo.

echo Cleaning stale temporary build files...
powershell -NoProfile -Command "Get-ChildItem -Path $env:TEMP -Filter '_MEI*' -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"

python -m PyInstaller --clean SubNovaStudio.spec
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo [SUCCESS] Build completed successfully!
    echo - Directory version:  dist\SubNovaStudio\SubNovaStudio.exe
    echo - Standalone version: dist\SubNovaStudio_Standalone.exe
    echo.
    echo Unblocking Windows Defender Mark-of-the-Web...
    powershell -NoProfile -Command "Get-ChildItem -Path 'dist' -Recurse -Filter '*.exe' | Unblock-File -ErrorAction SilentlyContinue"
    echo Updating Desktop Shortcut...
    python create_shortcut.py
    echo ===================================================
) else (
    echo.
    echo [ERROR] Build failed! Check the output above.
)
pause

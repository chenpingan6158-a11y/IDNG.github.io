@echo off
title Daily Report Dashboard
cd /d "%~dp0"

echo ============================================
echo   Daily Report Dashboard
echo   Browser will open automatically.
echo   Keep this window open while using it.
echo   To stop: close this window or press Ctrl+C
echo ============================================
echo.

".venv\Scripts\python.exe" main.py

echo.
echo Server stopped.
pause

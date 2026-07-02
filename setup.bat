@echo off
chcp 65001 >nul
title ClipFetch - Setup
echo ============================================
echo   ClipFetch - Setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.9+ from python.org
  echo         and tick "Add Python to PATH" during install.
  pause
  exit /b 1
)

echo Installing yt-dlp...
python -m pip install -U -r "%~dp0requirements.txt"

echo.
echo Checking / installing ffmpeg...
python "%~dp0clipfetch.py" --setup

echo.
echo ============================================
echo   Setup complete. Run start.bat to launch.
echo ============================================
pause

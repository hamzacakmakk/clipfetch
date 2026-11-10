@echo off
rem Builds dist\ClipFetch.exe, a single-file Windows app that needs no Python install.
rem Requirements: pip install -r requirements.txt pyinstaller
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name ClipFetch ^
  --icon assets\clipfetch.ico ^
  --collect-all curl_cffi ^
  --collect-submodules yt_dlp ^
  clipfetch.py
echo.
echo Built: %~dp0dist\ClipFetch.exe

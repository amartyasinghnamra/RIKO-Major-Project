@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv-tts\Scripts\python.exe" (
    echo [ERROR] RIKO environment not found. Run install.bat first.
    exit /b 1
)
".venv-tts\Scripts\python.exe" GUI\app.py
exit /b %errorlevel%

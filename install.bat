@echo off
setlocal EnableExtensions
title RIKO setup

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Could not enter the RIKO project folder.
    exit /b 1
)

echo.
echo ========================================
echo          RIKO Windows setup
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
    echo During setup, enable "Add python.exe to PATH", then open a new CMD window.
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was found on PATH but could not run.
    echo Install Python from https://www.python.org/downloads/windows/ and reopen CMD.
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [ERROR] RIKO requires Python 3.10 or newer. Install Python 3.11 or newer and retry.
    exit /b 1
)

where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama was not found on PATH.
    echo Install Ollama from https://ollama.com/download/windows, then open a new CMD window.
    exit /b 1
)

where curl.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl.exe was not found on PATH. Use a current Windows 10/11 installation or install curl, then retry.
    exit /b 1
)

if not exist requirements.txt (
    echo [ERROR] requirements.txt is missing. Run this installer from the RIKO repository.
    exit /b 1
)

if not exist .venv-tts\Scripts\python.exe (
    echo [1/6] Creating the project virtual environment...
    python -m venv .venv-tts
    if errorlevel 1 goto :failed
) else (
    echo [1/6] Reusing the existing .venv-tts environment...
)

echo [2/6] Installing Python packages from requirements.txt...
".venv-tts\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv-tts\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo [3/6] Preparing Kokoro model and voice assets...
if not exist models\kokoro mkdir models\kokoro
if errorlevel 1 goto :failed

call :ensure_asset "models\kokoro\kokoro-v1.0.int8.onnx" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" 80000000
if errorlevel 1 goto :failed
call :ensure_asset "models\kokoro\voices-v1.0.bin" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" 1000000
if errorlevel 1 goto :failed

call :setup_profile
if errorlevel 1 goto :failed

echo [5/7] Downloading the Ollama model qwen3:4b-instruct if needed...
ollama pull qwen3:4b-instruct
if errorlevel 1 goto :failed

echo [6/7] Downloading or checking the Faster-Whisper base model cache...
".venv-tts\Scripts\python.exe" -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('Faster-Whisper base model is ready.')"
if errorlevel 1 goto :failed

echo [7/7] Activating the project virtual environment for this CMD session...
endlocal & call ".venv-tts\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo.
echo Setup complete. This CMD session now uses .venv-tts.
echo From the repository root, run: python src\main.py
echo Choose Text Chat or Voice Chat from the RIKO menu.
echo.
exit /b 0

:ensure_asset
set "ASSET=%~1"
set "ASSET_URL=%~2"
set "MIN_BYTES=%~3"
if exist "%ASSET%" goto :validate_asset

set "PART=%ASSET%.part"
echo Downloading %ASSET%...
curl.exe --fail --location --retry 3 --retry-delay 2 --output "%PART%" "%ASSET_URL%"
if errorlevel 1 (
    echo [ERROR] Download failed: %ASSET_URL%
    echo A partial file, if any, is left as "%PART%" and can be replaced on retry.
    exit /b 1
)

for %%F in ("%PART%") do if %%~zF LSS %MIN_BYTES% (
    echo [ERROR] Downloaded file is unexpectedly small: "%PART%"
    echo The partial file has been kept for inspection; retry after checking the URL/network.
    exit /b 1
)

if exist "%ASSET%" (
    echo [ERROR] "%ASSET%" appeared during download. Keeping both files; review them manually.
    exit /b 1
)
for %%F in ("%ASSET%") do ren "%PART%" "%%~nxF"
if errorlevel 1 (
    echo [ERROR] Could not move the completed asset into place: "%ASSET%"
    exit /b 1
)

:validate_asset
for %%F in ("%ASSET%") do if %%~zF LSS %MIN_BYTES% (
    echo [ERROR] Existing asset is smaller than expected: "%ASSET%"
    echo It has not been changed or deleted. Move or replace it yourself, then retry.
    exit /b 1
)
echo Ready: %ASSET%
exit /b 0

:setup_profile
echo [4/7] Setting up your RIKO user profile...
if exist "config\local\user_profile.json" (
    echo Existing local profile found; keeping it unchanged.
    exit /b 0
)

".venv-tts\Scripts\python.exe" src\create_user_profile.py
if errorlevel 1 (
    echo [ERROR] The user profile setup script failed.
    exit /b 1
)
if not exist "config\local\user_profile.json" (
    echo No profile was saved. You can create one later with:
    echo python src\create_user_profile.py
)
exit /b 0

:failed
echo.
echo [ERROR] Setup stopped because a command failed. Fix the issue above and run install.bat again.
exit /b 1

@echo off
setlocal EnableExtensions
title RIKO setup
cd /d "%~dp0"
if errorlevel 1 goto :failed

echo.
echo ========================================
echo          RIKO Windows setup
echo ========================================
echo.

if not exist requirements.txt (
    echo [ERROR] requirements.txt is missing. Run this installer from the repository.
    exit /b 1
)
if not exist src\main.py (
    echo [ERROR] src\main.py is missing. The repository checkout is incomplete.
    exit /b 1
)
where curl.exe >nul 2>&1
if errorlevel 1 (
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] curl.exe is missing and winget is unavailable for automatic installation.
        echo Install curl and rerun install.bat.
        exit /b 1
    )
    echo curl.exe is missing. Installing it with winget...
    winget install --id cURL.cURL --exact --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :failed
    where curl.exe >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] curl was installed but is not on this CMD PATH yet. Open a new CMD window and rerun install.bat.
        exit /b 1
    )
)

call :find_python
if errorlevel 1 goto :failed
call :ensure_ollama
if errorlevel 1 goto :failed

echo [1/6] Creating or reusing the project virtual environment...
if not exist .venv-tts\Scripts\python.exe (
    %PYTHON_CMD% -m venv .venv-tts
    if errorlevel 1 goto :failed
) else (
    echo Reusing .venv-tts; existing environment will not be deleted.
)
".venv-tts\Scripts\python.exe" -c "import tkinter; print('Tkinter desktop GUI support is ready.')"
if errorlevel 1 (
    echo [ERROR] Tkinter is unavailable in this Python installation.
    echo Repair or reinstall Python with Tcl/Tk support, then rerun install.bat.
    exit /b 1
)

echo [2/6] Installing Python requirements...
".venv-tts\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv-tts\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo [3/6] Downloading Kokoro model and voice assets when missing...
if not exist models\kokoro mkdir models\kokoro
if errorlevel 1 goto :failed
call :ensure_asset "models\kokoro\kokoro-v1.0.int8.onnx" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" 80000000
if errorlevel 1 goto :failed
call :ensure_asset "models\kokoro\voices-v1.0.bin" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" 1000000
if errorlevel 1 goto :failed

echo [4/6] Ensuring Ollama is running and downloading the chat model...
call :start_ollama
if errorlevel 1 goto :failed
ollama pull qwen3:4b-instruct
if errorlevel 1 goto :failed

echo [5/6] Preparing the Faster-Whisper base model cache...
".venv-tts\Scripts\python.exe" -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('Faster-Whisper base model is ready.')"
if errorlevel 1 goto :failed

echo [6/6] Creating your local user profile, if you do not already have one...
if exist config\local\user_profile.json (
    echo Existing profile found and preserved.
) else (
    ".venv-tts\Scripts\python.exe" src\create_user_profile.py
    if errorlevel 1 goto :failed
)

echo.
echo Setup complete. Launch RIKO with: run.bat
echo Or launch the native desktop GUI with: run-gui.bat
echo Or activate .venv-tts and run: python src\main.py
echo.
exit /b 0

:find_python
set "PYTHON_CMD=python"
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0

where py >nul 2>&1
if not errorlevel 1 (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3.11"
        exit /b 0
    )
)

where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required and winget is unavailable for automatic setup.
    echo Install Python 3.11+ from https://www.python.org/downloads/windows/ and rerun.
    exit /b 1
)
echo Python 3.11 was not found. Installing it with winget...
winget install --id Python.Python.3.11 --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 exit /b 1
where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python installed, but the py launcher is not yet on PATH. Open a new CMD window and rerun install.bat.
    exit /b 1
)
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python installation needs a new CMD window. Rerun install.bat after opening one.
    exit /b 1
)
set "PYTHON_CMD=py -3.11"
exit /b 0

:ensure_ollama
where ollama >nul 2>&1
if not errorlevel 1 exit /b 0
where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama is missing and winget is unavailable.
    echo Install Ollama from https://ollama.com/download/windows and rerun install.bat.
    exit /b 1
)
echo Ollama was not found. Installing it with winget...
winget install --id Ollama.Ollama --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 exit /b 1
where ollama >nul 2>&1
if not errorlevel 1 exit /b 0
for %%F in ("%LOCALAPPDATA%\Programs\Ollama\ollama.exe" "%ProgramFiles%\Ollama\ollama.exe") do if exist "%%~F" set "OLLAMA_EXE=%%~F"
if defined OLLAMA_EXE (
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama;%ProgramFiles%\Ollama"
    exit /b 0
)
echo [ERROR] Ollama installed, but this CMD session cannot locate it. Open a new CMD window and rerun install.bat.
exit /b 1

:start_ollama
ollama list >nul 2>&1
if not errorlevel 1 exit /b 0
echo Starting the Ollama application/service...
start "" /b ollama serve
for /l %%I in (1,1,30) do (
    timeout /t 2 /nobreak >nul
    ollama list >nul 2>&1
    if not errorlevel 1 exit /b 0
)
echo [ERROR] Ollama did not become ready. Start Ollama and rerun install.bat.
exit /b 1

:ensure_asset
set "ASSET=%~1"
set "ASSET_URL=%~2"
set "MIN_BYTES=%~3"
if exist "%ASSET%" goto :validate_asset
set "PART=%ASSET%.part"
if exist "%PART%" (
    echo [ERROR] A previous partial download exists: "%PART%"
    echo Review or remove that partial file, then rerun the installer.
    exit /b 1
)
echo Downloading %ASSET%...
curl.exe --fail --location --retry 3 --retry-delay 2 --output "%PART%" "%ASSET_URL%"
if errorlevel 1 (
    echo [ERROR] Download failed. Partial file preserved at "%PART%".
    exit /b 1
)
for %%F in ("%PART%") do if %%~zF LSS %MIN_BYTES% (
    echo [ERROR] Downloaded file is unexpectedly small: "%PART%". It has been kept for inspection.
    exit /b 1
)
for %%F in ("%ASSET%") do ren "%PART%" "%%~nxF"
if errorlevel 1 exit /b 1
:validate_asset
for %%F in ("%ASSET%") do if %%~zF LSS %MIN_BYTES% (
    echo [ERROR] Existing asset is smaller than expected and was not changed: "%ASSET%"
    exit /b 1
)
echo Ready: %ASSET%
exit /b 0

:failed
echo.
echo [ERROR] Setup did not complete. Correct the reported issue and rerun install.bat.
exit /b 1

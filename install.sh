#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
trap 'status=$?; echo; echo "[ERROR] Setup stopped at line ${BASH_LINENO[0]} (exit ${status}). Correct the issue and rerun with: bash install.sh" >&2; exit "$status"' ERR
echo "========================================"
echo "          RIKO Linux setup"
echo "========================================"
[[ -f requirements.txt && -f src/main.py ]] || { echo "[ERROR] Run this script from a complete RIKO clone." >&2; exit 1; }
[[ "$(uname -s)" == Linux ]] || { echo "[ERROR] install.sh supports Linux only." >&2; exit 1; }
if ! command -v apt-get >/dev/null 2>&1; then
    echo "[ERROR] Automatic Linux dependency setup currently supports Debian/Ubuntu (apt-get)." >&2
    echo "Install Python 3.10+, venv/pip, a C build toolchain, PortAudio, libsndfile, libespeak-ng, curl, and Ollama manually." >&2
    exit 1
fi
if (( EUID == 0 )); then SUDO=; elif command -v sudo >/dev/null 2>&1; then SUDO=sudo; else
    echo "[ERROR] sudo is required to install system dependencies." >&2; exit 1
fi
echo "[1/7] Installing Linux runtime/build prerequisites..."
$SUDO apt-get update
$SUDO apt-get install -y python3 python3-venv python3-pip python3-dev build-essential pkg-config portaudio19-dev libsndfile1 libespeak-ng1 curl ca-certificates
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] python3 was not installed." >&2; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' || { echo "[ERROR] Python 3.10+ is required; this distro provides an older Python." >&2; exit 1; }
if ! command -v ollama >/dev/null 2>&1; then
    echo "[2/7] Installing Ollama using its official Linux installer..."
    curl -fsSL https://ollama.com/install.sh | $SUDO sh
else
    echo "[2/7] Ollama is already installed."
fi
echo "[3/7] Creating or reusing the project virtual environment..."
if [[ ! -x .venv-tts/bin/python ]]; then python3 -m venv .venv-tts; else echo "Reusing .venv-tts; existing environment will not be deleted."; fi
".venv-tts/bin/python" -m pip install --upgrade pip
".venv-tts/bin/python" -m pip install -r requirements.txt
echo "[4/7] Downloading Kokoro model and voice assets when missing..."
mkdir -p models/kokoro
ensure_asset() {
    local file="$1" url="$2" min_bytes="$3" part="$\{1}.part"
    if [[ -e "$file" ]]; then
        local size
        size="$(stat -c %s -- "$file")"
        (( size >= min_bytes )) || { echo "[ERROR] Existing asset is too small and was preserved: $file" >&2; return 1; }
        echo "Ready: $file"; return 0
    fi
    [[ ! -e "$part" ]] || { echo "[ERROR] Partial file already exists and was preserved: $part" >&2; return 1; }
    echo "Downloading $file..."
    curl --fail --location --retry 3 --retry-delay 2 --output "$part" "$url"
    local size
    size="$(stat -c %s -- "$part")"
    (( size >= min_bytes )) || { echo "[ERROR] Downloaded asset is too small; partial file kept: $part" >&2; return 1; }
    if [[ -e "$file" ]]; then echo "[ERROR] Destination appeared during download; keeping both files." >&2; return 1; fi
    mv -- "$part" "$file"
    echo "Ready: $file"
}
ensure_asset models/kokoro/kokoro-v1.0.int8.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx 80000000
ensure_asset models/kokoro/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin 1000000
echo "[5/7] Starting Ollama and downloading the chat model..."
if command -v systemctl >/dev/null 2>&1 && systemctl is-enabled ollama >/dev/null 2>&1; then
    $SUDO systemctl start ollama
else
    if ! pgrep -x ollama >/dev/null 2>&1; then nohup ollama serve >/tmp/riko-ollama.log 2>&1 </dev/null & fi
fi
ready=0
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then ready=1; break; fi
    sleep 2
done
(( ready == 1 )) || { echo "[ERROR] Ollama did not become ready; check its service/logs and rerun." >&2; exit 1; }
ollama pull qwen3:4b-instruct
echo "[6/7] Preparing the Faster-Whisper base model cache..."
".venv-tts/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('Faster-Whisper base model is ready.')"
echo "[7/7] Creating your local user profile, if you do not already have one..."
if [[ -e config/local/user_profile.json ]]; then
    echo "Existing profile found and preserved."
else
    ".venv-tts/bin/python" src/create_user_profile.py
fi
echo
echo "Setup complete. Launch RIKO with: bash run.sh"
echo "The project environment is .venv-tts; no shell activation is needed by run.sh."

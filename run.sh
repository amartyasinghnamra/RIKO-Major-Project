#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
if [[ ! -x .venv-tts/bin/python ]]; then
    echo "[ERROR] RIKO environment not found. Run: bash install.sh" >&2
    exit 1
fi
exec .venv-tts/bin/python src/main.py

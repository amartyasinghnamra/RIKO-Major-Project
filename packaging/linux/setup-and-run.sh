#!/usr/bin/env bash
set -Eeuo pipefail
APP_HOME="${1:?App data directory is required}"
cd "$APP_HOME"
trap 'status=$?; if (( status != 0 )); then echo; echo "[RIKO] Setup failed with exit code ${status}. Rerun the AppImage to try again." >&2; read -r -p "Press Enter to close this terminal..." _ || true; fi' EXIT
bash install.sh
touch .riko-setup-complete
bash run-gui.sh

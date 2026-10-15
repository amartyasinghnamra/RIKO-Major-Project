#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/build"
OUTPUT_DIR="$BUILD_ROOT/output"
OUTPUT_FILE="${1:-$OUTPUT_DIR/RIKO-x86_64.AppImage}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

command -v python3 >/dev/null || { echo "python3 is required." >&2; exit 1; }
command -v rsvg-convert >/dev/null || { echo "Install librsvg2-bin to provide rsvg-convert." >&2; exit 1; }
command -v desktop-file-validate >/dev/null || { echo "Install desktop-file-utils to provide desktop-file-validate." >&2; exit 1; }

python3 "$PROJECT_ROOT/packaging/stage_project.py" "$WORK_DIR/stage"
APP_DIR="$WORK_DIR/AppDir"
mkdir -p "$APP_DIR/usr/share/riko" "$(dirname -- "$OUTPUT_FILE")"
cp -a "$WORK_DIR/stage/." "$APP_DIR/usr/share/riko/"
cp "$SCRIPT_DIR/AppRun" "$APP_DIR/AppRun"
cp "$SCRIPT_DIR/riko.desktop" "$APP_DIR/riko.desktop"
desktop-file-validate "$APP_DIR/riko.desktop"
rsvg-convert --width 256 --height 256 --output "$APP_DIR/riko.png" "$SCRIPT_DIR/riko.svg"
chmod +x "$APP_DIR/AppRun" "$APP_DIR/usr/share/riko/riko-setup-and-run.sh"

APPIMAGETOOL="$WORK_DIR/appimagetool.AppImage"
curl --fail --location --retry 3 \
    --output "$APPIMAGETOOL" \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$APPIMAGETOOL"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 \
    "$APPIMAGETOOL" "$APP_DIR" "$OUTPUT_FILE"
printf 'Built AppImage: %s\n' "$OUTPUT_FILE"

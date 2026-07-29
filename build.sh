#!/usr/bin/env bash
set -e

echo "============================================"
echo "  GGU_VDOD - Portable Build Script"
echo "============================================"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 was not found on PATH."
  exit 1
fi

"$PYTHON_BIN" -m venv venv
VENV_PYTHON="venv/bin/python"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt pyinstaller
PYI_MODE="--onefile"
if [[ "${GGU_BUILD_MODE:-}" == "onedir" ]]; then
  PYI_MODE="--onedir"
fi
"$VENV_PYTHON" -m PyInstaller "$PYI_MODE" --collect-data ttkbootstrap --name GGU_VDOD app.py

if [[ -d "ffmpeg" ]]; then
  mkdir -p dist/ffmpeg
  cp -R ffmpeg/. dist/ffmpeg/
fi

echo
echo "Built executable: dist/GGU_VDOD"

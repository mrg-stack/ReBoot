#!/usr/bin/env bash
set -euo pipefail

# Launch ReBoot with a predictable environment for kiosk startup.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Default to fullscreen on kiosk hosts unless explicitly overridden.
export REBOOT_WINDOW_MODE="${REBOOT_WINDOW_MODE:-fullscreen}"

# Optional Qt hints for single-app kiosk sessions.
export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-1}"

cd "${PROJECT_ROOT}"

if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  echo "Missing virtual environment interpreter: ${PROJECT_ROOT}/.venv/bin/python" >&2
  exit 1
fi

exec "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/app/main.py"

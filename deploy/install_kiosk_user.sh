#!/usr/bin/env bash
set -euo pipefail

# Install ReBoot as a user-level kiosk app on Debian-like desktop sessions.
# This script installs both:
# 1) a systemd user service (preferred when user systemd session is active)
# 2) an XDG autostart desktop entry (fallback for desktop environments)

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
AUTOSTART_DIR="${HOME}/.config/autostart"
mkdir -p "${SYSTEMD_USER_DIR}" "${AUTOSTART_DIR}"

service_src="${PROJECT_ROOT}/deploy/reboot-kiosk.service"
desktop_src="${PROJECT_ROOT}/deploy/reboot-kiosk.desktop"
service_dst="${SYSTEMD_USER_DIR}/reboot-kiosk.service"
desktop_dst="${AUTOSTART_DIR}/reboot-kiosk.desktop"

if [[ ! -f "${service_src}" ]] || [[ ! -f "${desktop_src}" ]]; then
  echo "Missing kiosk templates under ${PROJECT_ROOT}/deploy" >&2
  exit 1
fi

# Install launcher executable.
chmod +x "${PROJECT_ROOT}/deploy/reboot-kiosk-launch.sh"

# Render templates with absolute project path.
sed "s|__REBOOT_ROOT__|${PROJECT_ROOT}|g" "${service_src}" > "${service_dst}"
sed "s|__REBOOT_ROOT__|${PROJECT_ROOT}|g" "${desktop_src}" > "${desktop_dst}"

# Enable and start the user service when a user systemd session is available.
if command -v systemctl >/dev/null 2>&1; then
  if systemctl --user daemon-reload >/dev/null 2>&1; then
    systemctl --user enable reboot-kiosk.service >/dev/null
    systemctl --user restart reboot-kiosk.service >/dev/null
    echo "Enabled systemd user service: ${service_dst}"
  else
    echo "systemctl --user is not active in this session; autostart desktop entry was still installed."
  fi
else
  echo "systemctl not found; autostart desktop entry was installed instead."
fi

echo "Installed desktop autostart entry: ${desktop_dst}"
echo "Done. Reboot or log out/in to verify boot-time launch."

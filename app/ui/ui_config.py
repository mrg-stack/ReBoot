# UI configuration shared by all screens.
#
# Design choice:
# - Every top-level screen calls apply_window_mode(...).
# - Linux defaults to fullscreen because Debian kiosk is the target runtime.
# - Developers can override mode with REBOOT_WINDOW_MODE.

from __future__ import annotations

import os
import platform
from PySide6.QtWidgets import QWidget

# Adjust these values to change the GUI window size.
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 850

# Runtime window mode selection.
# Linux defaults to fullscreen to match kiosk deployment.
# Accepted override values: windowed, maximized, fullscreen.
DEFAULT_WINDOW_MODE = "fullscreen" if platform.system() == "Linux" else "windowed"
WINDOW_MODE = os.getenv("REBOOT_WINDOW_MODE", DEFAULT_WINDOW_MODE).strip().lower()


def apply_window_mode(window: QWidget, title: str) -> None:
	# Centralized window behavior avoids mismatched mode between screens.
	# fullscreen: kiosk mode
	# maximized: desktop-filling but still managed by WM
	# fallback: fixed development window size
	window.setWindowTitle(title)

	if WINDOW_MODE == "fullscreen":
		window.showFullScreen()
		return

	if WINDOW_MODE == "maximized":
		window.showMaximized()
		return

	# Windowed mode keeps the design baseline used by current layouts.
	window.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

# Brand palette
PRIMARY_COLOR = "#3A4A6B"
ACCENT_COLOR = "#4CAF88"
BACKGROUND_COLOR = "#F2F4F7"
TEXT_COLOR = "#222222"
LINK_COLOR = "#464FEB"
BORDER_COLOR = "#E6E6E6"
SURFACE_COLOR = "#F5F5F5"

APP_STYLESHEET = f"""
QWidget {{
	background-color: {BACKGROUND_COLOR};
	color: {TEXT_COLOR};
}}

QPushButton {{
	background-color: {SURFACE_COLOR};
	color: {TEXT_COLOR};
	border: 1px solid {BORDER_COLOR};
	border-radius: 8px;
	padding: 10px;
	font-weight: 600;
}}

QPushButton:hover {{
	border: 1px solid {PRIMARY_COLOR};
}}

QPushButton:pressed {{
	background-color: #e9edf2;
}}

QPushButton:disabled {{
	color: #9b9b9b;
	border: 1px solid {BORDER_COLOR};
}}

QRadioButton, QCheckBox {{
	color: {TEXT_COLOR};
}}
"""
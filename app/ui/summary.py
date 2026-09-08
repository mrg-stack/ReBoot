"""Summary screen placeholder for final recommendation output."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from ui.ui_config import apply_window_mode, PRIMARY_COLOR, TEXT_COLOR


class SummaryScreen(QWidget):
    """Display a simple end-of-flow placeholder message."""

    def __init__(self):
        super().__init__()

        apply_window_mode(self, "ReBoot - Summary")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("Ready to proceed")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")

        info = QLabel("This is where final recommendations will be displayed")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        layout.addWidget(title)
        layout.addWidget(info)
        self.setLayout(layout)

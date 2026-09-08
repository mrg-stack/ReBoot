# Hardware analysis step in the guided flow.
#
# Runtime behavior:
# - Start with a short loading message.
# - Probe hardware details.
# - Replace loading widgets with summary widgets.
# - Continue to recommendation step.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer
from core.recommendation import RecommendationScreen
from services.hardware_report import UnsupportedPlatformError
from services.system_info import get_system_info
from ui.ui_config import apply_window_mode, PRIMARY_COLOR, TEXT_COLOR


class HardwareScreen(QWidget):
    # Collect and present system specifications to the user.

    def __init__(self):
        super().__init__()

        apply_window_mode(self, "ReBoot - Hardware Analysis")

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.setSpacing(20)

        # First render a clear loading state before running the probe.
        self.status_label = QLabel("Analysing your system...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")

        self.layout.addWidget(self.status_label)
        self.setLayout(self.layout)

        # Delay avoids instant flash from loading -> results on fast machines.
        QTimer.singleShot(2000, self.load_hardware_info)

    def load_hardware_info(self):
        # Fetch system info and replace loading state with detailed specs.
        try:
            info = get_system_info()
        except UnsupportedPlatformError as error:
            self.clear_layout()
            title = QLabel("Unsupported Runtime")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {PRIMARY_COLOR};")
            detail = QLabel(str(error))
            detail.setWordWrap(True)
            detail.setAlignment(Qt.AlignCenter)
            detail.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")
            self.layout.addWidget(title)
            self.layout.addWidget(detail)
            return
        cpu_model = info.get("cpu_model", info.get("cpu", "Unknown CPU"))
        cpu_arch = info.get("cpu_arch", "Unknown architecture")
        cpu_cores = info.get("cpu_cores", "Unknown cores")
        cpu_speed = info.get("cpu_speed", "Unknown speed")
        ram = info["ram"]
        disk = info["disk"]

        # Reuse the same screen and replace loading widgets with result widgets.
        self.clear_layout()

        title = QLabel("System Analysis Complete")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {PRIMARY_COLOR};")

        cpu_model_label = QLabel(f"CPU Model: {cpu_model}")
        cpu_arch_label = QLabel(f"Architecture: {cpu_arch}")
        cpu_cores_label = QLabel(f"Cores/Threads: {cpu_cores}")
        cpu_speed_label = QLabel(f"CPU Speed: {cpu_speed}")
        ram_label = QLabel(f"RAM: {ram}")
        disk_label = QLabel(f"Disk: {disk}")

        for label in [cpu_model_label, cpu_arch_label, cpu_cores_label, cpu_speed_label, ram_label, disk_label]:
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        self.layout.addWidget(title)
        self.layout.addWidget(cpu_model_label)
        self.layout.addWidget(cpu_arch_label)
        self.layout.addWidget(cpu_cores_label)
        self.layout.addWidget(cpu_speed_label)
        self.layout.addWidget(ram_label)
        self.layout.addWidget(disk_label)

        continue_btn = QPushButton("Continue")
        continue_btn.setMinimumHeight(44)
        continue_btn.clicked.connect(self.go_to_recommendation)
        self.layout.addWidget(continue_btn)

    def go_to_recommendation(self):
        # Open recommendation screen and close hardware analysis screen.
        self.recommendation_screen = RecommendationScreen()
        self.recommendation_screen.show()
        self.close()

    def clear_layout(self):
        # Clear child widgets so the same layout can be rebuilt safely.
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
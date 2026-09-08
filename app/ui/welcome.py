from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QColor, QLinearGradient
from ui.hardware import HardwareScreen
from ui.secure_erase import SecureEraseScreen
from ui.ui_config import apply_window_mode, TEXT_COLOR


class _ReBootLogo(QWidget):
    """Custom logo widget painting Re:Boot with gradient colon dots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font = QFont()
        self._font.setPixelSize(30)
        self._font.setBold(True)
        fm = QFontMetrics(self._font)
        self._re_w = fm.horizontalAdvance("Re")
        self._colon_w = 14
        self._boot_w = fm.horizontalAdvance("Boot")
        self._ascent = fm.ascent()
        self._height = fm.height()
        self.setFixedSize(self._re_w + self._colon_w + self._boot_w, self._height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self._font)
        baseline = self._ascent
        cap = int(self._ascent * 0.92)

        p.setPen(QColor(TEXT_COLOR))
        p.drawText(0, baseline, "Re")

        dot_r = 5
        dot_cx = self._re_w + 7
        top_cy = baseline - int(cap * 0.70)
        bot_cy = baseline - int(cap * 0.25)

        for cy, colors in [
            (top_cy, ("#78D6B4", "#4CAF88", "#319A73")),
            (bot_cy, ("#4F7DF3", "#2E67E8", "#1E4FC0")),
        ]:
            grad = QLinearGradient(dot_cx, cy - dot_r, dot_cx, cy + dot_r)
            grad.setColorAt(0, QColor(colors[0]))
            grad.setColorAt(0.52, QColor(colors[1]))
            grad.setColorAt(1, QColor(colors[2]))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(dot_cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)

        p.setPen(QColor(TEXT_COLOR))
        p.drawText(self._re_w + self._colon_w, baseline, "Boot")


class WelcomeScreen(QWidget):
    """First screen of the guided setup flow."""

    def __init__(self):
        super().__init__()

        apply_window_mode(self, "Re:Boot")

        layout = QVBoxLayout()

        # Keep content centered and readable on common window sizes.
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(_ReBootLogo())

        subtitle = QLabel("Prepare, secure and reinstall your PC in a few steps")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        # Helper function to create button containers with left-aligned icon and text.
        def create_icon_button(icon_text: str, title: str, description: str):
            container = QPushButton()
            container.setMinimumHeight(80)

            # Layout set directly on the QPushButton (no intermediate widget)
            # so that Qt hover state detection works the same as a plain button.
            layout = QHBoxLayout(container)
            layout.setSpacing(20)
            layout.setContentsMargins(20, 10, 20, 10)
            layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            icon_label = QLabel(icon_text)
            icon_label.setStyleSheet("font-size: 48px; background: transparent;")
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setFixedWidth(60)
            icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            title_label = QLabel(title)
            title_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_COLOR}; background: transparent;")
            title_label.setAlignment(Qt.AlignLeft)
            title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            desc_label = QLabel(description)
            desc_label.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR}; background: transparent;")
            desc_label.setAlignment(Qt.AlignLeft)
            desc_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setAlignment(Qt.AlignVCenter)
            text_layout.addWidget(title_label)
            text_layout.addWidget(desc_label)

            layout.addWidget(icon_label)
            layout.addLayout(text_layout)

            return container
        
        quick_btn = create_icon_button("⚡", "Quick Setup", "Recommended for most users")
        custom_btn = create_icon_button("⚙️", "Custom Setup", "Full control and options")
        erase_only_btn = create_icon_button("🧹", "Secure Erase Drive Only", "No OS installation")

        # Both options currently use the same next screen at POC stage.
        quick_btn.clicked.connect(self.quick_setup)
        custom_btn.clicked.connect(self.custom_setup)
        erase_only_btn.clicked.connect(self.secure_erase_only)

        layout.addLayout(logo_row)
        layout.addWidget(subtitle)
        layout.addWidget(quick_btn)
        layout.addWidget(custom_btn)
        layout.addWidget(erase_only_btn)

        self.setLayout(layout)

    def quick_setup(self):
        """Handle quick-start selection."""
        self.open_hardware_screen()

    def custom_setup(self):
        """Handle custom-start selection."""
        self.open_hardware_screen()

    def secure_erase_only(self):
        """Open secure erase flow directly without OS installation intent."""
        self.secure_erase_screen = SecureEraseScreen(previous_screen=self, install_os=False)
        self.secure_erase_screen.show()
        self.close()

    def open_hardware_screen(self):
        """Open hardware analysis and close the welcome screen."""
        self.hardware_screen = HardwareScreen()
        self.hardware_screen.show()
        self.close()
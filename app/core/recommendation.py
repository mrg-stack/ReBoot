# Recommendation step where user selects install intent.
#
# UI choice maps to two state fields:
# - selected_distro: mint, debian, none
# - install_os: True or False
#
# That state is passed to the secure erase step and later installer logic.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QRadioButton
from PySide6.QtCore import Qt
from core.secure_erase import SecureEraseScreen
from ui.ui_config import apply_window_mode, PRIMARY_COLOR, TEXT_COLOR


class RecommendationScreen(QWidget):
    # Show recommendation summary and capture distro preference.

    def __init__(self, plan=None):
        super().__init__()

        # Default path is beginner-friendly install until user changes option.
        self.selected_distro = "mint"
        self.install_os = True

        apply_window_mode(self, "ReBoot - Recommendation")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Recommended setup")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")

        self.suggestion = QLabel("We suggest Linux Mint for your system")
        self.suggestion.setAlignment(Qt.AlignCenter)
        self.suggestion.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        # Placeholder: profile engine is not wired yet.
        profile = QLabel("Suggested profile: Developer")
        profile.setAlignment(Qt.AlignCenter)
        profile.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        # Keep spacing between recommendation summary and user choice section.
        choice_title = QLabel("Choose your experience")
        choice_title.setAlignment(Qt.AlignCenter)
        choice_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PRIMARY_COLOR};")

        self.easy_radio = QRadioButton("Easy to use (Linux Mint)")
        self.easy_radio.setChecked(True)

        easy_desc = QLabel("Recommended for most users")
        easy_desc.setAlignment(Qt.AlignCenter)
        easy_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        self.advanced_radio = QRadioButton("Advanced setup (Debian)")

        advanced_desc = QLabel("More control and flexibility for experienced users")
        advanced_desc.setAlignment(Qt.AlignCenter)
        advanced_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        self.erase_only_radio = QRadioButton("Secure erase only (no OS installation)")
        erase_only_desc = QLabel("Erase data and generate certificate only. No operating system will be installed.")
        erase_only_desc.setAlignment(Qt.AlignCenter)
        erase_only_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        self.confirmation_label = QLabel("Great, we'll prepare an easy-to-use system.")
        self.confirmation_label.setAlignment(Qt.AlignCenter)
        self.confirmation_label.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        # Any radio change immediately updates both visible text and state.
        self.easy_radio.toggled.connect(self.update_experience_choice)
        self.advanced_radio.toggled.connect(self.update_experience_choice)
        self.erase_only_radio.toggled.connect(self.update_experience_choice)

        # Continue opens the secure erase confirmation step.
        continue_btn = QPushButton("Continue")
        continue_btn.setMinimumHeight(50)
        continue_btn.clicked.connect(self.continue_clicked)

        layout.addWidget(title)
        layout.addWidget(self.suggestion)
        layout.addWidget(profile)
        layout.addSpacing(12)
        layout.addWidget(choice_title)
        layout.addWidget(self.easy_radio)
        layout.addWidget(easy_desc)
        layout.addWidget(self.advanced_radio)
        layout.addWidget(advanced_desc)
        layout.addWidget(self.erase_only_radio)
        layout.addWidget(erase_only_desc)
        layout.addWidget(self.confirmation_label)
        layout.addWidget(continue_btn)

        self.setLayout(layout)

    def update_experience_choice(self):
        # Keep state and user-facing recommendation text in sync.
        # This is the single source of truth for install intent.
        if self.erase_only_radio.isChecked():
            self.selected_distro = "none"
            self.install_os = False
            self.suggestion.setText("You selected Secure erase only")
            self.confirmation_label.setText("Great, we'll erase the device and skip OS installation.")
            return

        if self.advanced_radio.isChecked():
            self.selected_distro = "debian"
            self.install_os = True
            self.suggestion.setText("You selected Debian")
            self.confirmation_label.setText("Great, we'll prepare an advanced setup.")
            return

        self.selected_distro = "mint"
        self.install_os = True
        self.suggestion.setText("We suggest Linux Mint for your system")
        self.confirmation_label.setText("Great, we'll prepare an easy-to-use system.")

    def continue_clicked(self):
        # Open secure erase step and hide the recommendation screen.
        self.secure_erase_screen = SecureEraseScreen(previous_screen=self, install_os=self.install_os)
        self.secure_erase_screen.show()
        self.close()

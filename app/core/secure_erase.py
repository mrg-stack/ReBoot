# Secure erase confirmation step (POC, non-destructive).
#
# Current behavior:
# - captures wipe preference and irreversible-action consent
# - records the chosen mode in memory
# - generates a simulated certificate document
#
# No destructive disk operation is performed in this build.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget
from services.certificate import generate_erase_certificate, open_certificate
from ui.ui_config import apply_window_mode, PRIMARY_COLOR, ACCENT_COLOR, TEXT_COLOR


class SecureEraseScreen(QWidget):
    # Collect wipe preference and explicit confirmation before proceeding.

    def __init__(self, previous_screen=None, install_os=True):
        super().__init__()

        self.previous_screen = previous_screen
        self.install_os = install_os
        self.wipe_method = "secure"
        self.confirmed = False

        apply_window_mode(self, "ReBoot - Secure Disk Erase")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Secure Disk Erase")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")

        explanation = QLabel(
            "Before installing a new operating system, ReBoot will erase all data on the main disk.\n"
            "This helps protect personal data, prevent recovery of previous information, and prepare the device for safe reuse."
        )
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        explanation.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        warning = QLabel("Warning: this process is irreversible. All existing files and accounts will be permanently removed.")
        warning.setWordWrap(True)
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet(f"font-size: 13px; color: {ACCENT_COLOR};")

        post_wipe_note = QLabel(
            "After erase: OS installation is enabled."
            if self.install_os
            else "After erase: OS installation is skipped (erase only mode)."
        )
        post_wipe_note.setWordWrap(True)
        post_wipe_note.setAlignment(Qt.AlignCenter)
        post_wipe_note.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        options_title = QLabel("Choose erase method")
        options_title.setAlignment(Qt.AlignCenter)
        options_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PRIMARY_COLOR};")

        self.quick_radio = QRadioButton("Quick erase")
        quick_desc = QLabel(
            "Fast, suitable for reuse within the same organisation. "
            "Planned approach: verified single-pass overwrite for HDDs."
        )
        quick_desc.setWordWrap(True)
        quick_desc.setAlignment(Qt.AlignCenter)
        quick_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        self.secure_radio = QRadioButton("Secure erase (GDPR compliant)")
        self.secure_radio.setChecked(True)
        secure_desc = QLabel(
            "More thorough, recommended for sensitive data and GDPR-style compliance. "
            "Planned approach: firmware-level erase on SSDs (ATA Secure Erase / NVMe Sanitize)."
        )
        secure_desc.setWordWrap(True)
        secure_desc.setAlignment(Qt.AlignCenter)
        secure_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR};")

        compliance_note = QLabel(
            "For GDPR-style compliance, choose Secure erase: it is intended to render data irrecoverable and "
            "supports accountable erasure workflows, including certificate-ready reporting."
        )
        compliance_note.setWordWrap(True)
        compliance_note.setAlignment(Qt.AlignCenter)
        compliance_note.setStyleSheet(f"font-size: 13px; color: {PRIMARY_COLOR};")

        # Collect report metadata from the operator before certificate generation.
        metadata_title = QLabel("Certificate details")
        metadata_title.setAlignment(Qt.AlignCenter)
        metadata_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PRIMARY_COLOR};")

        self.asset_id_input = QLineEdit()
        self.asset_id_input.setPlaceholderText("Asset ID")

        self.operator_name_input = QLineEdit()
        self.operator_name_input.setPlaceholderText("Operator name")
        self.operator_name_input.setText("ReBoot Operator")

        self.chassis_type_combo = QComboBox()
        self.chassis_type_combo.addItems(
            [
                "Workstation",
                "Laptop",
                "Desktop",
                "Mini PC",
                "Server",
                "Other",
            ]
        )

        self.confirm_checkbox = QCheckBox("I understand that all data will be permanently deleted")
        self.confirm_checkbox.setStyleSheet("font-size: 13px;")

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setMinimumHeight(50)
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.continue_clicked)

        back_btn = QPushButton("Back")
        back_btn.setMinimumHeight(44)
        back_btn.clicked.connect(self.go_back)

        # Form controls update state continuously; continue button stays locked
        # until user explicitly confirms destructive intent.
        self.quick_radio.toggled.connect(self.update_wipe_method)
        self.secure_radio.toggled.connect(self.update_wipe_method)
        self.confirm_checkbox.toggled.connect(self.update_confirmation_state)

        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(warning)
        layout.addWidget(post_wipe_note)
        layout.addSpacing(12)
        layout.addWidget(options_title)
        layout.addWidget(self.quick_radio)
        layout.addWidget(quick_desc)
        layout.addWidget(self.secure_radio)
        layout.addWidget(secure_desc)
        layout.addWidget(compliance_note)
        layout.addSpacing(8)
        layout.addWidget(metadata_title)
        layout.addWidget(self.asset_id_input)
        layout.addWidget(self.operator_name_input)
        layout.addWidget(self.chassis_type_combo)
        layout.addWidget(self.confirm_checkbox)
        layout.addWidget(self.continue_btn)
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def update_wipe_method(self):
        # Persist wipe mode from the selected radio option.
        if self.quick_radio.isChecked():
            self.wipe_method = "quick"
            return
        self.wipe_method = "secure"

    def update_confirmation_state(self):
        # Require explicit confirmation before allowing continue.
        self.confirmed = self.confirm_checkbox.isChecked()
        self.continue_btn.setEnabled(self.confirmed)

    def go_back(self):
        # Return to the previous screen in the flow.
        if self.previous_screen is not None:
            self.previous_screen.show()
        self.close()

    def continue_clicked(self):
        # Handle continue after confirmation and trigger POC wipe path.
        if not self.confirmed:
            return

        print(f"Wipe method selected: {self.wipe_method}")
        print(f"Post-wipe mode: {'install_os' if self.install_os else 'erase_only'}")
        self.perform_wipe()

    def perform_wipe(self):
        # POC wipe implementation.
        #
        # This intentionally does not touch block devices yet. It validates
        # flow and produces a certificate artifact while backend erase logic
        # is built separately.
        # TODO: detect drive type (HDD/SSD/NVMe) and choose method accordingly.
        # Quick path target: verified single-pass overwrite for HDD media.
        # Secure path target: firmware-level erase for SSD/NVMe (ATA Secure Erase / NVMe Sanitize).
        # TODO: write an auditable erasure report and support certificate generation.
        # This POC intentionally performs no destructive action.
        print("Secure erase is not executed in this POC build.")

        report_metadata = {
            "asset_id": self.asset_id_input.text().strip(),
            "operator_name": self.operator_name_input.text().strip(),
            "chassis_type": self.chassis_type_combo.currentText().strip(),
        }

        certificate_path = generate_erase_certificate(self.wipe_method, report_metadata)
        print(f"Certificate generated: {certificate_path}")
        open_certificate(certificate_path)

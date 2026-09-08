# Secure erase confirmation step (POC, non-destructive).
#
# Current behavior:
# - captures wipe preference and irreversible-action consent
# - records the chosen mode in memory
# - generates a factual hardware analysis report
#
# No destructive disk operation is performed in this build.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from services.certificate import generate_erase_certificate, generate_hardware_report, open_certificate
from services.hardware_report import UnsupportedPlatformError
from ui.ui_config import apply_window_mode, PRIMARY_COLOR, ACCENT_COLOR, TEXT_COLOR


class SecureEraseScreen(QWidget):
    # Collect wipe preference and explicit confirmation before proceeding.

    def __init__(self, previous_screen=None, install_os=True, development_mode=False):
        super().__init__()

        self.previous_screen = previous_screen
        self.install_os = install_os
        self.development_mode = bool(development_mode)
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
            "Select the erasure method that a future backend should use.\n"
            "This build analyzes hardware and records the request; it does not erase any disk."
        )
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        explanation.setStyleSheet(f"font-size: 14px; color: {TEXT_COLOR};")

        warning = QLabel(
            "Analysis only: no erasure is performed, and the generated report is not proof of data sanitization."
        )
        warning.setWordWrap(True)
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet(f"font-size: 13px; color: {ACCENT_COLOR};")

        simulation_warning = QLabel(
            "Developer simulation active — only fictional AMD64 Linux data will be "
            "reported; no real hardware is analyzed and the report is not valid evidence."
        )
        simulation_warning.setWordWrap(True)
        simulation_warning.setAlignment(Qt.AlignCenter)
        simulation_warning.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {ACCENT_COLOR};"
        )
        simulation_warning.setVisible(self.development_mode)

        post_wipe_note = QLabel(
            "After analysis: OS installation is planned but not started by this step."
            if self.install_os
            else "After analysis: OS installation is skipped."
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
            "Secure erase is the recommended future method for sensitive data. "
            "The current analysis report does not establish GDPR compliance."
        )
        compliance_note.setWordWrap(True)
        compliance_note.setAlignment(Qt.AlignCenter)
        compliance_note.setStyleSheet(f"font-size: 13px; color: {PRIMARY_COLOR};")

        # Collect report metadata from the operator before certificate generation.
        metadata_title = QLabel("Report details")
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

        self.confirm_checkbox = QCheckBox(
            "I understand that this build records the request but does not erase data"
        )
        self.confirm_checkbox.setStyleSheet("font-size: 13px;")

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setMinimumHeight(50)
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.continue_clicked)

        back_btn = QPushButton("Back")
        back_btn.setMinimumHeight(44)
        back_btn.clicked.connect(self.go_back)

        # Form controls update state continuously; continue button stays locked
        # until the user acknowledges the analysis-only behavior.
        self.quick_radio.toggled.connect(self.update_wipe_method)
        self.secure_radio.toggled.connect(self.update_wipe_method)
        self.confirm_checkbox.toggled.connect(self.update_confirmation_state)

        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(warning)
        layout.addWidget(simulation_warning)
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
        # Handle continue after acknowledgement and generate the report.
        if not self.confirmed:
            return

        print(f"Wipe method selected: {self.wipe_method}")
        print(f"Post-wipe mode: {'install_os' if self.install_os else 'erase_only'}")
        self.perform_wipe()

    def perform_wipe(self):
        # Analysis-only milestone.
        #
        # This intentionally does not touch block devices yet. It validates
        # flow and produces a factual report artifact while backend erase logic
        # is built separately.
        # TODO: detect drive type (HDD/SSD/NVMe) and choose method accordingly.
        # Quick path target: verified single-pass overwrite for HDD media.
        # Secure path target: firmware-level erase for SSD/NVMe (ATA Secure Erase / NVMe Sanitize).
        # This POC intentionally performs no destructive action.
        print("Hardware analysis only; secure erase is not executed in this build.")

        report_metadata = {
            "asset_id": self.asset_id_input.text().strip(),
            "operator_name": self.operator_name_input.text().strip(),
            "chassis_type": self.chassis_type_combo.currentText().strip(),
        }

        report_generator = generate_hardware_report if self.install_os else generate_erase_certificate
        try:
            report_path = report_generator(
                self.wipe_method,
                report_metadata,
                development_mode=getattr(self, "development_mode", False),
            )
        except UnsupportedPlatformError as error:
            QMessageBox.critical(
                self,
                "Hardware report unavailable",
                str(error),
            )
            return
        print(f"Hardware analysis report generated: {report_path}")
        open_certificate(report_path)

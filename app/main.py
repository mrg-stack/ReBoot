# Application entry point for the ReBoot desktop UI.
#
# Keep this module small and explicit:
# 1) create QApplication
# 2) apply global stylesheet
# 3) show WelcomeScreen
# 4) enter Qt event loop

import sys
from PySide6.QtWidgets import QApplication
from ui.welcome import WelcomeScreen
from ui.ui_config import APP_STYLESHEET


def main():
    # Startup sequence for the guided UI flow.
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    window = WelcomeScreen()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
"""Qt application bootstrap kept separate from window composition."""

import sys

from PySide6.QtWidgets import QApplication

from .main_window import QtMainWindow
from .theme import apply_dark_theme
from .tooltip import install_animated_tooltips


def create_qt_application(arguments=None):
    """Create the shared Qt application instance and apply its base theme."""
    from PySide6.QtCore import Qt
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication.instance() or QApplication(arguments or sys.argv)
    application.setApplicationName("GGU_VDOD")
    apply_dark_theme(application)
    install_animated_tooltips(application)
    return application


def run_qt_application(arguments=None):
    """Run the Qt window. Not the production entry point until feature parity."""
    application = create_qt_application(arguments)
    window = QtMainWindow()
    window.show()
    return application.exec()

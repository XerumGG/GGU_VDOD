"""Qt application bootstrap kept separate from window composition."""

import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QDialog

from .main_window import QtMainWindow
from .theme import apply_dark_theme
from .tooltip import install_animated_tooltips


class PopupWindowPolicy(QObject):
    """Give every custom Qt popup native Windows window controls and resizing."""

    def eventFilter(self, watched, event):
        if isinstance(watched, QDialog) and event.type() == QEvent.Type.Polish:
            flags = watched.windowFlags()
            watched.setWindowFlags(
                flags
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            watched.setSizeGripEnabled(True)
        return super().eventFilter(watched, event)


def install_popup_window_policy(application):
    """Install the dialog policy once so future popups receive normal title bars."""
    if application.property("ggu_popup_window_policy") is None:
        policy = PopupWindowPolicy(application)
        application.installEventFilter(policy)
        application.setProperty("ggu_popup_window_policy", policy)


def create_qt_application(arguments=None):
    """Create the shared Qt application instance and apply its base theme."""
    from PySide6.QtCore import Qt
    from ...services.crash import install_crash_handlers

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication.instance() or QApplication(arguments or sys.argv)
    application.setApplicationName("GGU_VDOD")
    install_crash_handlers()
    apply_dark_theme(application)
    install_animated_tooltips(application)
    install_popup_window_policy(application)
    return application


def run_qt_application(arguments=None):
    """Run the Qt window. Not the production entry point until feature parity."""
    application = create_qt_application(arguments)
    window = QtMainWindow()
    window.show()
    return application.exec()

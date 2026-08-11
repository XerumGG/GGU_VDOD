"""Test package for GGU_VDOD."""

import atexit
import os
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _cleanup_qt_widgets(delete_tooltip=False):
    try:
        from PySide6.QtWidgets import QApplication
        from ggu_vdod.ui.qt.tooltip import SmoothAnimatedToolTip
    except Exception:
        return

    app = QApplication.instance()
    if app is None:
        return

    for widget in list(app.topLevelWidgets()):
        try:
            if type(widget).__name__ == "SmoothAnimatedToolTip" and not delete_tooltip:
                widget.hide()
                continue
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            pass
    if delete_tooltip:
        SmoothAnimatedToolTip._instance = None
    app.processEvents()
    app.processEvents()


_original_test_case_run = unittest.TestCase.run


def _run_test_case_with_qt_cleanup(self, result=None):
    try:
        return _original_test_case_run(self, result)
    finally:
        _cleanup_qt_widgets(delete_tooltip=False)


unittest.TestCase.run = _run_test_case_with_qt_cleanup
atexit.register(lambda: _cleanup_qt_widgets(delete_tooltip=True))

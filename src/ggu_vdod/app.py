"""Application composition root.

This module connects the desktop UI to the application entry point. Business
logic remains in its existing implementation while the codebase is migrated
module by module.
"""

from .ui.qt.application import run_qt_application


def main() -> None:
    """Create and run the desktop application using PySide6."""
    run_qt_application()

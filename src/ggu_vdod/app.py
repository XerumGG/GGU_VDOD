"""Application composition root.

This module connects the desktop UI to the application entry point. Business
logic remains in its existing implementation while the codebase is migrated
module by module.
"""

from .ui.main_window import GGUVDODApp


def main() -> None:
    """Create and run the desktop application."""
    window = GGUVDODApp()
    window.mainloop()

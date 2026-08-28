"""Qt application bootstrap kept separate from window composition."""

import os
import sys
import ctypes


# Keep the bundled Qt DLLs ahead of any Qt installation on the user's PATH.
# Without this, Windows can load a different Qt6Core.dll before PySide6's
# matching library and report the misleading "specified procedure could not
# be found" import error.
_QT_DLL_HANDLES = []
_QT_NATIVE_HANDLES = []


def _qt_diagnostic(message):
    """Write optional frozen-startup diagnostics without affecting normal runs."""
    if not os.environ.get("GGU_QT_DIAGNOSTICS"):
        return
    try:
        with open(
            os.path.join(os.environ.get("TEMP", os.getcwd()), "GGU_VDOD_qt_bootstrap.log"),
            "a",
            encoding="utf-8",
        ) as diagnostic_file:
            diagnostic_file.write(f"{message}\n")
    except OSError:
        pass


def _load_native_library(path):
    """Load a DLL by absolute path without PyInstaller's ctypes redirection."""
    if os.name != "nt":
        return ctypes.CDLL(path)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    load_library = kernel32.LoadLibraryExW
    load_library.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
    load_library.restype = ctypes.c_void_p
    handle = load_library(path, None, 0)
    if not handle:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, ctypes.FormatError(error_code), path)
    return handle


def _prepare_bundled_qt_dll_search_path():
    _qt_diagnostic(f"frozen={getattr(sys, 'frozen', False)} executable={sys.executable}")
    if not getattr(sys, "frozen", False) or not hasattr(os, "add_dll_directory"):
        _qt_diagnostic("skip: not frozen or add_dll_directory unavailable")
        return

    executable_dir = os.path.dirname(sys.executable)
    meipass_dir = getattr(sys, "_MEIPASS", "")
    roots = [
        meipass_dir,
        os.path.join(executable_dir, "_internal"),
        executable_dir,
    ]
    bundle_root = next(
        (
            root
            for root in dict.fromkeys(root for root in roots if root)
            if os.path.isdir(os.path.join(root, "PySide6"))
        ),
        "",
    )
    if not bundle_root:
        _qt_diagnostic("no bundled PySide6 directory found")
        return

    for directory in (
        bundle_root,
        os.path.join(bundle_root, "shiboken6"),
        os.path.join(bundle_root, "PySide6"),
    ):
        if not os.path.isdir(directory):
            continue
        _qt_diagnostic(f"dll directory candidate={directory}")
        try:
            _QT_DLL_HANDLES.append(os.add_dll_directory(directory))
        except OSError:
            _qt_diagnostic(f"add_dll_directory failed={directory}")
            continue
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
        _qt_diagnostic(f"dll directory active={directory}")

    # PySide6's extension modules refer to both Qt6Core and Shiboken by name.
    # Preloading the matching files prevents Python/Windows from resolving a
    # same-named DLL from another Qt or Python installation on the machine.
    native_candidates = [
        os.path.join(bundle_root, "shiboken6", "shiboken6.abi3.dll"),
        os.path.join(bundle_root, "PySide6", "Qt6Core.dll"),
        os.path.join(bundle_root, "PySide6", "pyside6.abi3.dll"),
    ]
    for path in native_candidates:
        if not os.path.isfile(path):
            _qt_diagnostic(f"native missing={path}")
            continue
        try:
            _QT_NATIVE_HANDLES.append(_load_native_library(path))
            _qt_diagnostic(f"native loaded={path}")
        except OSError as error:
            _qt_diagnostic(f"native load failed={path}: {error}")
            continue

    _qt_diagnostic(f"native handles={len(_QT_NATIVE_HANDLES)}")


_prepare_bundled_qt_dll_search_path()

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

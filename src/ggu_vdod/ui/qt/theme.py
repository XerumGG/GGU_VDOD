"""The initial dark Qt palette and stylesheet for GGU_VDOD."""

from PySide6.QtGui import QColor, QPalette


WINDOW_BACKGROUND = "#000000"
PANEL_BACKGROUND = "#0a0a0a"
INPUT_BACKGROUND = "#111111"
TEXT = "#f2f2f2"
MUTED_TEXT = "#a7a7a7"
BORDER = "#303030"
ACCENT = "#e5484d"
ACCENT_HOVER = "#c53f43"
SUCCESS = "#57c26a"


def apply_dark_theme(application):
    """Apply the pitch-black baseline theme before custom theming migrates."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(WINDOW_BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(INPUT_BACKGROUND))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_BACKGROUND))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL_BACKGROUND))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    application.setPalette(palette)
    application.setStyleSheet(
        f"""
        QMainWindow, QWidget {{ background: {WINDOW_BACKGROUND}; color: {TEXT}; }}
        QFrame#panel {{ background: {PANEL_BACKGROUND}; border: 1px solid {BORDER}; border-radius: 8px; }}
        QLabel#muted {{ color: {MUTED_TEXT}; }}
        QLineEdit, QPlainTextEdit, QComboBox {{
            background: {INPUT_BACKGROUND}; color: {TEXT}; border: 1px solid {BORDER};
            border-radius: 5px; padding: 7px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
        QPushButton {{ background: {PANEL_BACKGROUND}; border: 1px solid {BORDER}; border-radius: 5px; padding: 8px 14px; }}
        QPushButton:hover {{ border-color: {ACCENT}; }}
        QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: {TEXT}; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
        QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; text-align: center; min-height: 16px; }}
        QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
        QMenuBar, QMenu {{ background: {PANEL_BACKGROUND}; color: {TEXT}; }}
        QMenu::item:selected {{ background: {ACCENT}; }}
        QGroupBox {{
            background: {PANEL_BACKGROUND}; border: 1px solid {BORDER}; border-radius: 6px;
            margin-top: 10px; padding-top: 12px; font-weight: 600; color: {TEXT};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px;
            color: {MUTED_TEXT}; font-size: 13px;
        }}
        QCheckBox, QRadioButton {{ color: {TEXT}; spacing: 8px; padding: 3px 0; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px; border: 1px solid #555555; border-radius: 3px; background: #111111;
        }}
        QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
        QCheckBox::indicator:checked {{
            border-color: {ACCENT}; background: {ACCENT};
        }}
        QRadioButton::indicator {{
            width: 16px; height: 16px; border: 1px solid #555555; border-radius: 8px; background: #111111;
        }}
        QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
        QRadioButton::indicator:checked {{
            border-color: {ACCENT}; background: #111111;
        }}
        """
    )


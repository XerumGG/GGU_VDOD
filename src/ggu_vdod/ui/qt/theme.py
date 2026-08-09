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


def apply_dark_theme(application, base_font_size=10):
    """Apply the pitch-black baseline theme with proportional font scaling for uniform UI zooming."""
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

    fz = max(7, int(base_font_size))
    fz_sm = max(6, fz - 1)

    application.setStyleSheet(
        f"""
        QMainWindow, QWidget {{ background: {WINDOW_BACKGROUND}; color: {TEXT}; font-size: {fz}pt; }}
        QFrame#panel {{ background: {PANEL_BACKGROUND}; border: 1px solid {BORDER}; border-radius: 8px; }}
        QLabel#muted {{ color: {MUTED_TEXT}; font-size: {fz_sm}pt; }}
        QLineEdit, QPlainTextEdit, QComboBox {{
            background: {INPUT_BACKGROUND}; color: {TEXT}; border: 1px solid {BORDER};
            border-radius: 5px; padding: 6px; font-size: {fz}pt;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
        QPushButton {{
            background: #141414; color: {TEXT}; border: 1px solid #383838;
            border-radius: 6px; padding: 6px 14px; font-size: {fz}pt; font-weight: 500; min-height: 24px;
        }}
        QPushButton:hover {{ border-color: {ACCENT}; background: #1f1f1f; }}
        QPushButton:pressed {{ background: #282828; }}
        QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: #ffffff; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
        QPushButton#primary:pressed {{ background: #a33337; }}
        QPushButton:disabled {{ background: #0f0f0f; color: #555555; border-color: #222222; }}
        QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; text-align: center; min-height: 16px; font-size: {fz_sm}pt; }}
        QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
        QMenuBar, QMenu {{ background: {PANEL_BACKGROUND}; color: {TEXT}; font-size: {fz}pt; }}
        QMenu::item:selected {{ background: {ACCENT}; }}
        QGroupBox {{
            background: {PANEL_BACKGROUND}; border: 1px solid {BORDER}; border-radius: 6px;
            margin-top: 12px; padding-top: 14px; font-weight: 600; color: {TEXT}; font-size: {fz}pt;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px;
            color: {MUTED_TEXT}; font-size: {fz_sm}pt;
        }}
        QCheckBox, QRadioButton {{
            color: {TEXT}; spacing: 8px; background: transparent; padding: 4px 0; font-size: {fz}pt;
        }}
        QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; background: {WINDOW_BACKGROUND}; }}
        QTabBar::tab {{
            background: {INPUT_BACKGROUND}; color: {MUTED_TEXT}; border: 1px solid {BORDER};
            padding: 8px 18px; font-weight: 500; border-top-left-radius: 6px; border-top-right-radius: 6px;
            margin-right: 4px; font-size: {fz}pt;
        }}
        QTabBar::tab:selected {{ background: #1c1c1c; color: #ffffff; border-bottom-color: {ACCENT}; font-weight: 600; }}
        QTabBar::tab:hover {{ color: #ffffff; background: #181818; }}
        QTableWidget {{ gridline-color: #222222; border: 1px solid {BORDER}; background: #080808; selection-background-color: #2a2a2a; font-size: {fz}pt; }}
        QHeaderView::section {{ background: #121212; color: {MUTED_TEXT}; padding: 6px; border: 1px solid #222222; font-weight: 600; font-size: {fz_sm}pt; }}
        """
    )

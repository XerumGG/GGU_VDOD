"""Shared Qt theme and typography policy for GGU_VDOD.

Keeping colors, font sizes, and spacing here prevents individual dialogs and
widgets from drifting into different visual proportions.
"""

from copy import deepcopy
import re

from PySide6.QtGui import QColor, QPalette


DEFAULT_THEME = {
    "window_background": "#000000",
    "panel_background": "#0a0a0a",
    "input_background": "#111111",
    "log_background": "#080808",
    "text": "#f2f2f2",
    "muted_text": "#a7a7a7",
    "border": "#303030",
    "accent": "#e5484d",
    "accent_hover": "#c53f43",
    "success": "#57c26a",
}

THEME_PRESETS = {
    "Dark": DEFAULT_THEME,
    "Faint": {
        **DEFAULT_THEME,
        "window_background": "#101010",
        "panel_background": "#181818",
        "input_background": "#202020",
        "log_background": "#0c0c0c",
        "border": "#424242",
        "accent": "#8ab4f8",
        "accent_hover": "#6f9fe8",
    },
    "Orange": {
        **DEFAULT_THEME,
        "accent": "#ff8a1f",
        "accent_hover": "#e6730c",
    },
    "Green Hacker": {
        **DEFAULT_THEME,
        "window_background": "#020702",
        "panel_background": "#071107",
        "input_background": "#0d1b0d",
        "log_background": "#010401",
        "text": "#d7f9d7",
        "muted_text": "#86b886",
        "border": "#1d5b2b",
        "accent": "#31c45b",
        "accent_hover": "#239944",
        "success": "#68e68a",
    },
}

THEME_COLOR_FIELDS = (
    ("window_background", "Window background"),
    ("panel_background", "Panel background"),
    ("input_background", "Input background"),
    ("log_background", "Log background"),
    ("text", "Main text"),
    ("muted_text", "Muted text"),
    ("border", "Borders"),
    ("accent", "Accent"),
    ("accent_hover", "Accent hover"),
    ("success", "Success text"),
)

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Typography and spacing are deliberately small and stable. Zoom changes the
# base size, while these ratios keep labels, fields, and headings proportional.
BASE_FONT_SIZE = 10
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 18
BASE_SPACING = 10
BASE_MARGIN = 16


def is_valid_theme_color(value):
    """Return whether *value* is a complete six-digit hex color."""
    return bool(HEX_COLOR_RE.fullmatch(str(value or "").strip()))


def normalize_theme(theme=None):
    """Return a safe complete theme, falling back to Dark per invalid field."""
    source = theme if isinstance(theme, dict) else {}
    result = deepcopy(DEFAULT_THEME)
    for key, _label in THEME_COLOR_FIELDS:
        value = source.get(key)
        if is_valid_theme_color(value):
            result[key] = value.strip().lower()
    return result


def theme_name(theme):
    """Return a matching preset name or ``Custom`` for edited colors."""
    normalized = normalize_theme(theme)
    for name, preset in THEME_PRESETS.items():
        if normalized == normalize_theme(preset):
            return name
    return "Custom"


def _font_size(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = BASE_FONT_SIZE
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, value))


def apply_theme(application, theme=None, base_font_size=BASE_FONT_SIZE):
    """Apply palette, stylesheet, and the shared application font policy."""
    colors = normalize_theme(theme)
    window = colors["window_background"]
    panel = colors["panel_background"]
    input_bg = colors["input_background"]
    log_bg = colors["log_background"]
    text = colors["text"]
    muted = colors["muted_text"]
    border = colors["border"]
    accent = colors["accent"]
    accent_hover = colors["accent_hover"]
    success = colors["success"]

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(input_bg))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(panel))
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.Button, QColor(panel))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#666666"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#666666"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666666"))
    application.setPalette(palette)
    application.setProperty("ggu_theme", deepcopy(colors))

    fz = _font_size(base_font_size)
    fz_sm = max(MIN_FONT_SIZE, fz - 1)
    fz_lg = min(MAX_FONT_SIZE + 4, fz + 6)
    font = application.font()
    font.setPointSize(fz)
    application.setFont(font)

    application.setStyleSheet(
        f"""
        QMainWindow, QWidget {{ background: {window}; color: {text}; font-size: {fz}pt; }}
        QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; }}
        QLabel#muted {{ color: {muted}; font-size: {fz_sm}pt; }}
        QLabel#pageTitle {{ color: {text}; font-size: {fz_lg}pt; font-weight: 700; }}
        QLabel#sectionTitle {{ color: {text}; font-size: {min(MAX_FONT_SIZE + 2, fz + 2)}pt; font-weight: 600; }}
        QLabel#version {{ color: {accent}; font-size: {fz_sm}pt; font-weight: 700; padding-left: 10px; }}
        QLabel#success {{ color: {success}; }}
        QLabel#warning {{ color: #e5b84d; }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
            background: {input_bg}; color: {text}; border: 1px solid {border};
            border-radius: 5px; padding: 6px; font-size: {fz}pt;
        }}
        QPlainTextEdit#logBox {{ background: {log_bg}; font-family: Consolas, monospace; font-size: {fz_sm}pt; }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {accent}; }}
        QPushButton, QToolButton {{
            background: {panel}; color: {text}; border: 1px solid {border};
            border-radius: 6px; padding: 6px 14px; font-size: {fz}pt;
            font-weight: 500; min-height: 24px;
        }}
        QPushButton:hover, QToolButton:hover {{ border-color: {accent}; background: {input_bg}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {accent_hover}; }}
        QPushButton#primary, QToolButton#primary {{ background: {accent}; border-color: {accent}; color: #ffffff; font-weight: 600; }}
        QPushButton#primary:hover, QToolButton#primary:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
        QPushButton:disabled, QToolButton:disabled {{ background: {window}; color: {muted}; border-color: {border}; }}
        QProgressBar {{ border: 1px solid {border}; border-radius: 4px; text-align: center; min-height: 16px; font-size: {fz_sm}pt; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
        QMenuBar, QMenu {{ background: {panel}; color: {text}; font-size: {fz}pt; }}
        QMenu::item:selected {{ background: {accent}; }}
        QGroupBox {{
            background: {panel}; border: 1px solid {border}; border-radius: 6px;
            margin-top: 12px; padding-top: 14px; font-weight: 600;
            color: {text}; font-size: {fz}pt;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px;
            color: {muted}; font-size: {fz_sm}pt;
        }}
        QCheckBox, QRadioButton {{ color: {text}; spacing: 8px; background: transparent; padding: 4px 0; font-size: {fz}pt; }}
        QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; background: {window}; }}
        QTabBar::tab {{
            background: {input_bg}; color: {muted}; border: 1px solid {border};
            padding: 8px 18px; font-weight: 500; border-top-left-radius: 6px;
            border-top-right-radius: 6px; margin-right: 4px; font-size: {fz}pt;
        }}
        QTabBar::tab:selected {{ background: {panel}; color: {text}; border-bottom-color: {accent}; font-weight: 600; }}
        QTabBar::tab:hover {{ color: {text}; background: {input_bg}; }}
        QTableWidget {{ gridline-color: {border}; border: 1px solid {border}; background: {log_bg}; selection-background-color: {panel}; font-size: {fz}pt; }}
        QHeaderView::section {{ background: {panel}; color: {muted}; padding: 6px; border: 1px solid {border}; font-weight: 600; font-size: {fz_sm}pt; }}
        QScrollBar:vertical, QScrollBar:horizontal {{ background: {window}; border: none; }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {border}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
        QScrollBar::handle:hover {{ background: {accent}; }}
        QToolTip {{ background: {panel}; color: {text}; border: 1px solid {accent}; padding: 6px; font-size: {fz_sm}pt; }}
        """
    )


def apply_dark_theme(application, base_font_size=BASE_FONT_SIZE):
    """Backward-compatible entry point for the pitch-black default theme."""
    apply_theme(application, DEFAULT_THEME, base_font_size)

"""Shared Qt theme and typography policy for GGU_VDOD.

The theme system is intentionally semantic: widgets consume roles such as
window/panel/input/text/accent instead of hard-coded colors.  This keeps every
page, dialog and control visually consistent when the user switches themes.
"""

from copy import deepcopy
import re

from PySide6.QtGui import QColor, QPalette


# ---------------------------------------------------------------------------
# Theme presets
# ---------------------------------------------------------------------------
# The palettes avoid absolute black/white wherever possible.  That reduces
# harsh contrast while keeping normal text comfortably readable for long
# sessions.  Light themes use dark text and dark-theme presets use soft-white
# text instead of pure white.

DEFAULT_THEME = {
    "window_background": "#000000",
    "panel_background": "#000000",
    "input_background": "#08030356",
    "log_background": "#0f1116",
    "text": "#ffffff",
    "muted_text": "#939597",
    "border": "#303540",
    "accent": "#e62727e7",
    "accent_hover": "#8f0808e6",
    "accent_text": "#ffffff",
    "success": "#70d6a0",
    "warning": "#efc77c",
}

THEME_PRESETS = {
    # Balanced everyday dark theme.  This is the recommended default.
    "Dark": DEFAULT_THEME,

    # Low-saturation dark grey for long sessions / reduced visual fatigue.
    "Grey": {
        **DEFAULT_THEME,
        "window_background": "#191a1d",
        "panel_background": "#191a1d",
        "input_background": "#282a2e",
        "log_background": "#151619",
        "text": "#c2c4cd",
        "muted_text": "#96989e",
        "border": "#36383d",
        "accent": "#a7a9ad",
        "accent_hover": "#e3e6eb",
        "accent_text": "#17181b",
        "success": "#56ce8c",
        "warning": "#efc77c",
    },

    # Clean light theme.  Slightly warm neutrals prevent the starkness of
    # pure white while retaining strong text contrast.
    "White": {
        **DEFAULT_THEME,
        "window_background": "#ffffff",
        "panel_background": "#ffffff",
        "input_background": "#eff5f5",
        "log_background": "#f5f5f699",
        "text": "#0F0E0E",
        "muted_text": "#333334",
        "border": "#abafb7",
        "accent": "#565758",
        "accent_hover": "#2a2a2b",
        "accent_text": "#ffffff",
        "success": "#278457",
        "warning": "#9a6d00",
    },

    # A softer light-grey option for users who find a white UI too bright.
    "Light Grey": {
        **DEFAULT_THEME,
        "window_background": "#a8abb0",
        "panel_background": "#a8abb0",
        "input_background": "#969494",
        "log_background": "#656666",
        "text": "#27292d",
        "muted_text": "#686d75",
        "border": "#8b8c90",
        "accent": "#565758",
        "accent_hover": "#2a2a2b",
        "accent_text": "#989393",
        "success": "#385e4c",
        "warning": "#8c6800",
    },

    "Orange": {
        **DEFAULT_THEME,
        "accent": "#f2a35a",
        "accent_hover": "#dc8740",
        "accent_text": "#21170e",
    },

    "Midnight Blue": {
        **DEFAULT_THEME,
        "window_background": "#020127",
        "panel_background": "#020B1C",
        "input_background": "#202c43",
        "log_background": "#0c1220",
        "text": "#e7edf8",
        "muted_text": "#9ba8bc",
        "border": "#34425a",
        "accent": "#79a8ff",
        "accent_hover": "#456bb3",
        "accent_text": "#0d1628",
        "success": "#291ef3",
        "warning": "#8f81e8",
    },

    "Soft Rose": {
        **DEFAULT_THEME,
        "window_background": "#271D22",
        "panel_background": "#271D22",
        "input_background": "#2b2025",
        "log_background": "#120e10",
        "text": "#f0e7ea",
        "muted_text": "#b39da4",
        "border": "#46343b",
        "accent": "#e7a0b5",
        "accent_hover": "#dc5983",
        "accent_text": "#26151c",
        "success": "#fb21e5",
        "warning": "#f79efa",
    },

            "Purple": {
        **DEFAULT_THEME,
        "window_background": "#1d1928",
        "panel_background": "#1d1928",
        "input_background": "#272033",
        "log_background": "#100e15",
        "text": "#eeeaf7",
        "muted_text": "#9288ab",
        "border": "#393047",
        "accent": "#b79cff",
        "accent_hover": "#765bc1",
        "accent_text": "#17111f",
        "success": "#662dec",
        "warning": "#be90f3",
    },

            "Natural Green": {
        **DEFAULT_THEME,
        "window_background": "#101613",
        "panel_background": "#101613",
        "input_background": "#1d2720",
        "log_background": "#0b100d",
        "text": "#dcefe2",
        "muted_text": "#91ab98",
        "border": "#30483a",
        "accent": "#5bd48a",
        "accent_hover": "#2c814e",
        "accent_text": "#0c1a11",
        "success": "#7ee8a7",
        "warning": "#d8c17b",
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
    ("accent_text", "Accent text"),
    ("success", "Success text"),
    ("warning", "Warning text"),
)

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# Typography and spacing are deliberately stable. Zoom changes the base size,
# while these ratios keep labels, fields and headings proportional.
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
    accent_text = colors["accent_text"]
    success = colors["success"]
    warning = colors["warning"]

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(input_bg))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(panel))
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.Button, QColor(panel))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(accent_text))

    disabled = QColor(muted)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)

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
        QMainWindow, QWidget {{
            background: {window};
            color: {text};
            font-size: {fz}pt;
        }}

        QFrame#panel {{
            background: {panel};
            border: 1px solid {border};
            border-radius: 8px;
        }}

        QLabel#muted {{
            color: {muted};
            font-size: {fz_sm}pt;
        }}

        QLabel#pageTitle {{
            color: {text};
            font-size: {fz_lg}pt;
            font-weight: 700;
        }}

        QLabel#sectionTitle {{
            color: {text};
            font-size: {min(MAX_FONT_SIZE + 2, fz + 2)}pt;
            font-weight: 600;
        }}

        QLabel#version {{
            color: {accent};
            font-size: {fz_sm}pt;
            font-weight: 700;
            padding-left: 10px;
        }}

        QLabel#success {{ color: {success}; }}
        QLabel#warning {{ color: {warning}; }}

        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
            background: {input_bg};
            color: {text};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 8px;
            font-size: {fz}pt;
            selection-background-color: {accent};
            selection-color: {accent_text};
        }}

        QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover {{
            border-color: {accent_hover};
        }}

        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {accent};
        }}

        QPlainTextEdit#logBox {{
            background: {log_bg};
            color: {text};
            border-color: {border};
            font-family: Consolas, "Cascadia Mono", monospace;
            font-size: {fz_sm}pt;
        }}

        QPushButton, QToolButton {{
            background: {panel};
            color: {text};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: {fz}pt;
            font-weight: 500;
            min-height: 24px;
        }}

        QPushButton:hover, QToolButton:hover {{
            border-color: {accent};
            background: {input_bg};
        }}

        QPushButton:pressed, QToolButton:pressed {{
            background: {accent_hover};
            color: {accent_text};
            border-color: {accent_hover};
        }}

        QPushButton#primary, QToolButton#primary {{
            background: {accent};
            border-color: {accent};
            color: {accent_text};
            font-weight: 600;
        }}

        QPushButton#primary:hover, QToolButton#primary:hover {{
            background: {accent_hover};
            border-color: {accent_hover};
            color: {accent_text};
        }}

        QPushButton:disabled, QToolButton:disabled {{
            background: {window};
            color: {muted};
            border-color: {border};
        }}

        QProgressBar {{
            background: {input_bg};
            color: {text};
            border: 1px solid {border};
            border-radius: 4px;
            text-align: center;
            min-height: 16px;
            font-size: {fz_sm}pt;
        }}

        QProgressBar::chunk {{
            background: {accent};
            border-radius: 3px;
        }}

        QMenuBar {{
            background: {panel};
            color: {text};
            font-size: {fz}pt;
            border-bottom: 1px solid {border};
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 5px 9px;
        }}

        QMenuBar::item:selected {{
            background: {input_bg};
            color: {text};
        }}

        QMenu {{
            background: {panel};
            color: {text};
            border: 1px solid {border};
            padding: 4px;
            font-size: {fz}pt;
        }}

        QMenu::item {{
            padding: 6px 24px 6px 10px;
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background: {accent};
            color: {accent_text};
        }}

        QMenu::separator {{
            height: 1px;
            background: {border};
            margin: 4px 8px;
        }}

        QGroupBox {{
            background: {panel};
            border: 1px solid {border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 14px;
            font-weight: 600;
            color: {text};
            font-size: {fz}pt;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            color: {muted};
            font-size: {fz_sm}pt;
        }}

        QCheckBox, QRadioButton {{
            color: {text};
            spacing: 8px;
            background: transparent;
            padding: 4px 0;
            font-size: {fz}pt;
        }}

        QCheckBox:hover, QRadioButton:hover {{
            color: {accent};
        }}

        QTabWidget::pane {{
            border: 1px solid {border};
            border-radius: 6px;
            background: {window};
            top: -1px;
        }}

        QTabBar::tab {{
            background: {input_bg};
            color: {muted};
            border: 1px solid {border};
            padding: 8px 18px;
            font-weight: 500;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 4px;
            font-size: {fz}pt;
        }}

        QTabBar::tab:selected {{
            background: {panel};
            color: {text};
            border-bottom: 2px solid {accent};
            font-weight: 600;
        }}

        QTabBar::tab:hover {{
            color: {text};
            background: {input_bg};
            border-color: {accent_hover};
        }}

        QTableWidget {{
            gridline-color: {border};
            border: 1px solid {border};
            background: {log_bg};
            color: {text};
            selection-background-color: {accent};
            selection-color: {accent_text};
            font-size: {fz}pt;
        }}

        QTableWidget::item:hover {{
            background: {input_bg};
        }}

        QHeaderView::section {{
            background: {panel};
            color: {muted};
            padding: 6px;
            border: 1px solid {border};
            font-weight: 600;
            font-size: {fz_sm}pt;
        }}

        QScrollBar:vertical, QScrollBar:horizontal {{
            background: {window};
            border: none;
        }}

        QScrollBar:vertical {{
            width: 12px;
            margin: 2px;
        }}

        QScrollBar:horizontal {{
            height: 12px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: {border};
            border-radius: 5px;
            min-height: 28px;
            min-width: 28px;
        }}

        QScrollBar::handle:hover {{
            background: {accent_hover};
        }}

        QScrollBar::add-line, QScrollBar::sub-line,
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
            border: none;
        }}

        QToolTip {{
            background: {panel};
            color: {text};
            border: 1px solid {accent};
            border-radius: 4px;
            padding: 6px;
            font-size: {fz_sm}pt;
        }}

        QComboBox QAbstractItemView {{
            background: {panel};
            color: {text};
            border: 1px solid {border};
            selection-background-color: {accent};
            selection-color: {accent_text};
            outline: none;
        }}
        """
    )


def apply_dark_theme(application, base_font_size=BASE_FONT_SIZE):
    """Backward-compatible entry point for the balanced dark default theme."""
    apply_theme(application, DEFAULT_THEME, base_font_size)

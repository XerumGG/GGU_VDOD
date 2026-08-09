"""Smooth Animated ToolTip system with fade-in/out transitions for PySide6."""

from PySide6.QtCore import QEvent, QObject, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget


class SmoothAnimatedToolTip(QFrame):
    """Floating custom tooltip widget with smooth fade-in and fade-out animations."""

    _instance = None

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QFrame#ToolTipFrame {
                background-color: #161616;
                color: #f0f0f0;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            QLabel {
                color: #f0f0f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                padding: 4px 8px;
            }
        """)
        self.setObjectName("ToolTipFrame")

        # Layout & Text Label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        # Subtle Drop Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        # Fade Animations
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_tooltip)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def show_tooltip(self, text: str, pos: QPoint):
        if not text.strip():
            self.hide_tooltip()
            return

        self.label.setText(text)
        self.adjustSize()

        # Keep tooltip on screen boundaries
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        w, h = self.width(), self.height()
        x = pos.x() + 12
        y = pos.y() + 16

        if x + w > screen_geo.right():
            x = pos.x() - w - 6
        if y + h > screen_geo.bottom():
            y = pos.y() - h - 6

        self.move(max(screen_geo.left(), x), max(screen_geo.top(), y))

        # Fade-in animation (0.0 -> 0.95 opacity in 180ms)
        self._fade_anim.stop()
        self.setWindowOpacity(0.0)
        self.show()

        self._fade_anim.setDuration(180)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(0.95)
        self._fade_anim.start()

        # Auto hide after 6 seconds of static display
        self._hide_timer.stop()
        self._hide_timer.start(6000)

    def hide_tooltip(self):
        if not self.isVisible():
            return
        self._hide_timer.stop()
        self._fade_anim.stop()
        self._fade_anim.setDuration(140)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_fade_out_finished)
        self._fade_anim.start()

    def _on_fade_out_finished(self):
        try:
            self._fade_anim.finished.disconnect(self._on_fade_out_finished)
        except Exception:
            pass
        self.hide()


class AnimatedToolTipFilter(QObject):
    """Global Qt Event Filter capturing QEvent.ToolTip to display smooth animated tooltips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tooltip = SmoothAnimatedToolTip.get_instance()
        self._last_target = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip:
            if isinstance(watched, QWidget):
                curr = watched
                text = ""
                while curr:
                    if hasattr(curr, "toolTip") and curr.toolTip() and curr.toolTip().strip():
                        text = curr.toolTip().strip()
                        break
                    curr = curr.parentWidget()
                if text:
                    self._last_target = watched
                    self._tooltip.show_tooltip(text, QCursor.pos())
                    return True
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            self._tooltip.hide_tooltip()

        return super().eventFilter(watched, event)


def install_animated_tooltips(application: QApplication):
    """Install animated tooltip filter on the global QApplication instance."""
    filter_obj = AnimatedToolTipFilter(application)
    application.installEventFilter(filter_obj)
    return filter_obj

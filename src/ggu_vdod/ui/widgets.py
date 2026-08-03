"""Reusable Tk widgets used by the desktop window."""

import tkinter as tk

try:
    import ttkbootstrap as ttkb
except ImportError:
    ttkb = None


class UndoEntry(ttkb.Entry if ttkb is not None else tk.Entry):
    """Entry widget with portable undo/redo support."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._history = [self.get()]
        self._history_index = 0
        self._internal_edit = False
        self.bind("<KeyRelease>", self._capture_edit, add="+")
        self.bind("<<Cut>>", self._capture_after_virtual_edit, add="+")
        self.bind("<<Paste>>", self._capture_after_virtual_edit, add="+")
        self.bind("<FocusIn>", self._sync_external_value, add="+")

    def _sync_external_value(self, _event=None):
        current = self.get()
        if current != self._history[self._history_index]:
            self._history = [current]
            self._history_index = 0

    def _capture_after_virtual_edit(self, _event=None):
        self.after_idle(self._capture_edit)

    def _capture_edit(self, _event=None):
        if self._internal_edit:
            return
        current = self.get()
        if current == self._history[self._history_index]:
            return
        if self._history_index < len(self._history) - 1:
            self._history = self._history[:self._history_index + 1]
        self._history.append(current)
        self._history_index += 1

    def _restore_history_value(self, index):
        self._internal_edit = True
        try:
            self.delete(0, "end")
            self.insert(0, self._history[index])
        finally:
            self._internal_edit = False

    def edit_undo(self):
        self._sync_external_value()
        if self._history_index > 0:
            self._history_index -= 1
            self._restore_history_value(self._history_index)

    def edit_redo(self):
        self._sync_external_value()
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._restore_history_value(self._history_index)


class Tooltip:
    """Small animated help popup shown when the pointer rests over a widget."""

    def __init__(self, widget, text, delay_ms=300, colors_provider=None):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.colors_provider = colors_provider or (lambda: {
            "background": "#0b0b0b", "foreground": "#f4f4f4", "border": "#4a4a4a",
        })
        self.window = None
        self.show_after_id = None
        self.fade_id = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel_timer("show_after_id")
        self._cancel_timer("fade_id")
        self.show_after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel_timer("show_after_id")
        if self.window is not None:
            self._fade_out()

    def _cancel_timer(self, attribute):
        timer_id = getattr(self, attribute)
        if timer_id is not None:
            try:
                self.widget.after_cancel(timer_id)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

    def _show(self):
        self.show_after_id = None
        if self.window is not None:
            self._fade_in()
            return
        try:
            colors = self.colors_provider()
            window = tk.Toplevel(self.widget)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.configure(bg=colors["background"])
            label = tk.Label(
                window, text=self.text, justify="left", wraplength=360,
                bg=colors["background"], fg=colors["foreground"], padx=12, pady=8,
                relief="solid", bd=1, highlightthickness=1,
                highlightbackground=colors["border"], font=("Segoe UI", 10),
            )
            label.pack()
            window.update_idletasks()
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            screen_w = self.widget.winfo_screenwidth()
            popup_w = window.winfo_reqwidth()
            if x + popup_w > screen_w - 8:
                x = max(8, screen_w - popup_w - 8)
            window.geometry(f"+{x}+{y}")
            self.window = window
            try:
                window.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
            self._fade_in()
        except tk.TclError:
            self.window = None

    def _fade_in(self, alpha=0.0):
        if self.window is None or not self.window.winfo_exists():
            return
        alpha = min(alpha + 0.12, 1.0)
        try:
            self.window.attributes("-alpha", alpha)
        except tk.TclError:
            alpha = 1.0
        if alpha < 1.0:
            self.fade_id = self.widget.after(18, self._fade_in, alpha)

    def _fade_out(self, alpha=1.0):
        if self.window is None:
            return
        self._cancel_timer("fade_id")
        alpha -= 0.16
        if alpha <= 0.0:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
            return
        try:
            self.window.attributes("-alpha", alpha)
        except tk.TclError:
            alpha = 0.0
        self.fade_id = self.widget.after(18, self._fade_out, alpha)

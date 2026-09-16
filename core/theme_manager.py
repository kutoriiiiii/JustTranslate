# -*- coding: utf-8 -*-
"""Theme manager providing dark, light, and system theme switching for Just Translate."""

import sys
from typing import Optional
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QApplication
from config.settings import settings


class ThemeManager(QObject):
    """Manages application themes ('dark', 'light', 'system').
    
    Emits theme_changed(mode: str, is_dark: bool) when the theme changes.
    """
    theme_changed = Signal(str, bool)

    _instance: Optional["ThemeManager"] = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_os_listener()

    @classmethod
    def get_instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _setup_os_listener(self):
        """Attaches to Qt's styleHints colorSchemeChanged signal if available."""
        app = QApplication.instance()
        if app is not None:
            hints = app.styleHints()
            if hasattr(hints, "colorSchemeChanged"):
                try:
                    hints.colorSchemeChanged.connect(self._on_os_scheme_changed)
                except Exception:
                    pass

    def _on_os_scheme_changed(self, *args):
        """Callback when the operating system switches between dark and light mode."""
        if self.get_mode() == "system":
            self.apply_theme()

    def get_mode(self) -> str:
        """Returns the configured theme mode: 'dark', 'light', or 'system'."""
        mode = settings.get("app_theme", "dark")
        if mode not in ("dark", "light", "system"):
            mode = "dark"
        return mode

    def detect_os_theme(self) -> str:
        """Detects whether the underlying OS is currently in dark or light mode."""
        # 1. Qt 6.5+ styleHints colorScheme
        app = QApplication.instance()
        if app is not None:
            hints = app.styleHints()
            if hasattr(hints, "colorScheme"):
                scheme = hints.colorScheme()
                if scheme == Qt.ColorScheme.Dark:
                    return "dark"
                elif scheme == Qt.ColorScheme.Light:
                    return "light"

        # 2. Windows registry detection
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return "light" if value == 1 else "dark"
            except Exception:
                pass

        # 3. macOS defaults command detection
        if sys.platform == "darwin":
            try:
                import subprocess
                res = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if "Dark" in res.stdout:
                    return "dark"
                return "light"
            except Exception:
                pass

        # Default fallback
        return "dark"

    def is_dark(self) -> bool:
        """Returns True if the active presentation should be dark, False if light."""
        mode = self.get_mode()
        if mode == "dark":
            return True
        elif mode == "light":
            return False
        elif mode == "system":
            return self.detect_os_theme() == "dark"
        return True

    def apply_theme(self, mode: Optional[str] = None):
        """Applies the specified theme (or current mode from settings) to QApplication."""
        if mode is not None and mode in ("dark", "light", "system"):
            settings.set("app_theme", mode)
            settings.save()

        active_mode = self.get_mode()
        dark = self.is_dark()

        from ui.styles.modern_theme import get_theme_qss
        qss = get_theme_qss(dark)

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)

        self.theme_changed.emit(active_mode, dark)

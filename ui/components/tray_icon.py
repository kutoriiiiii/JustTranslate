# -*- coding: utf-8 -*-
"""System tray icon integration for Just Translate."""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal
from pathlib import Path

class AppTrayIcon(QSystemTrayIcon):
    """System tray icon with quick actions and window toggle."""

    restore_window_requested = Signal()
    mode_switch_requested = Signal(str)
    open_settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None, icon_path: Path = None):
        super().__init__(parent)
        self.icon_path = icon_path
        if icon_path and icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        self.setToolTip("Just Translate - 智能翻译、润色与词典")

        self._init_menu()
        self.activated.connect(self._on_tray_activated)

    def _init_menu(self):
        menu = QMenu()

        # 显示主窗口
        self.action_show = QAction("显示主窗口", self)
        self.action_show.triggered.connect(self.restore_window_requested.emit)
        menu.addAction(self.action_show)

        menu.addSeparator()

        # 模式切换
        self.action_translate = QAction("翻译模式", self)
        self.action_translate.triggered.connect(lambda: self.mode_switch_requested.emit("translate"))
        menu.addAction(self.action_translate)

        self.action_polish = QAction("润色模式", self)
        self.action_polish.triggered.connect(lambda: self.mode_switch_requested.emit("polish"))
        menu.addAction(self.action_polish)

        self.action_dict = QAction("词典模式", self)
        self.action_dict.triggered.connect(lambda: self.mode_switch_requested.emit("dictionary"))
        menu.addAction(self.action_dict)

        menu.addSeparator()

        # 设置
        self.action_settings = QAction("设置", self)
        self.action_settings.triggered.connect(self.open_settings_requested.emit)
        menu.addAction(self.action_settings)

        menu.addSeparator()

        # 退出程序
        self.action_quit = QAction("退出程序", self)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(self.action_quit)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        # 单击或双击托盘图标切换窗口显示
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_window_requested.emit()

    def notify(self, title: str, message: str, msecs: int = 3000):
        """Displays balloon notification message."""
        self.showMessage(title, message, QSystemTrayIcon.Information, msecs)

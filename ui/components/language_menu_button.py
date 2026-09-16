# -*- coding: utf-8 -*-
"""Custom language selector button with visual separator, two recent slots, and cascading secondary menu."""

from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QAction

from config.settings import settings
from config.languages import COMMON_LANGUAGES, EXTRA_LANGUAGES, get_language_label

class LanguageMenuButton(QPushButton):
    """Button providing a hierarchical menu with core languages, 2 recent other language slots, and a cascading sub-menu."""

    language_selected = Signal(str)

    def __init__(self, is_src: bool = False, parent=None):
        super().__init__(parent)
        self.is_src = is_src
        self.current_code = "Auto" if is_src else "English"
        
        # 样式由全局主题 QSS (comboLikeBtn) 统一接管
        self.setObjectName("comboLikeBtn")
        self.setCursor(Qt.PointingHandCursor)

        self._update_button_text()
        self.clicked.connect(self._show_menu)

    def get_current_code(self) -> str:
        return self.current_code

    def set_current_language(self, code: str, emit_signal: bool = True):
        self.current_code = code
        # 若选择的是扩展语种，记入该方向的最近使用槽位
        if code not in ("Auto", "Chinese", "English", "Japanese"):
            settings.add_recent_other_lang(self.is_src, code)
        
        self._update_button_text()
        if emit_signal:
            self.language_selected.emit(code)

    def _update_button_text(self):
        label = get_language_label(self.current_code)
        self.setText(f"{label}  ▾")

    def _show_menu(self):
        menu = QMenu(self)

        # 1. 常用语言区 (Common Languages)
        if self.is_src:
            self._add_lang_action(menu, "\u81ea\u52a8\u8bc6\u522b (Auto)", "Auto")
        
        for label, code in COMMON_LANGUAGES:
            self._add_lang_action(menu, label, code)

        # 2. 视觉分隔线
        menu.addSeparator()

        # 3. 两个“其他语言”记忆槽位 (Recent Other Language Slots)
        recents = settings.get_recent_other_langs(self.is_src)
        slot1_code = recents[0] if len(recents) > 0 else "Korean"
        slot2_code = recents[1] if len(recents) > 1 else "French"

        # 槽位1
        label1 = f"{get_language_label(slot1_code)}  [\u69fd\u4f4d 1]"
        self._add_lang_action(menu, label1, slot1_code)

        # 槽位2
        label2 = f"{get_language_label(slot2_code)}  [\u69fd\u4f4d 2]"
        self._add_lang_action(menu, label2, slot2_code)

        # 4. 视觉分隔线
        menu.addSeparator()

        # 5. 二级级联子菜单 (Cascading Sub-Menu for More Languages)
        sub_menu = menu.addMenu("\u66f4\u591a\u4e3b\u6d41\u8bed\u79cd (More) \u276f")
        for label, code in EXTRA_LANGUAGES:
            self._add_lang_action(sub_menu, label, code)

        # 弹出菜单对齐按钮底部
        pos = self.mapToGlobal(QPoint(0, self.height() + 2))
        menu.exec(pos)

    def _add_lang_action(self, parent_menu: QMenu, label: str, code: str):
        action = QAction(label, parent_menu)
        action.setCheckable(True)
        if self.current_code == code:
            action.setChecked(True)
        action.triggered.connect(lambda checked=False, c=code: self.set_current_language(c))
        parent_menu.addAction(action)

# -*- coding: utf-8 -*-
"""Top control bar for selecting modes, languages, and active model profile."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, 
    QLabel, QButtonGroup, QSpacerItem, QSizePolicy, QMenu
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction, QActionGroup
from config.settings import settings
from core.theme_manager import ThemeManager
from ui.components.language_menu_button import LanguageMenuButton
from ui.components.api_status_indicator import ApiStatusIndicator

class ControlBar(QFrame):
    """Top bar containing mode buttons, language pickers, model selector, and settings."""

    mode_changed = Signal(str)
    languages_changed = Signal(str, str)
    profile_changed = Signal(str)
    open_settings_requested = Signal()
    open_history_requested = Signal()
    swap_requested = Signal()
    eco_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlBar")
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # ----------------------------------------------------
        # 第一排：核心业务交互（模式分段按钮 + 语言对选择）
        # ----------------------------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # 1. 模式选择 (Segmented buttons)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_translate = QPushButton("翻译")
        self.btn_translate.setObjectName("modeBtn")
        self.btn_translate.setCheckable(True)
        self.btn_translate.setCursor(Qt.PointingHandCursor)

        self.btn_polish = QPushButton("润色")
        self.btn_polish.setObjectName("modeBtn")
        self.btn_polish.setCheckable(True)
        self.btn_polish.setCursor(Qt.PointingHandCursor)

        self.btn_dictionary = QPushButton("词典")
        self.btn_dictionary.setObjectName("modeBtn")
        self.btn_dictionary.setCheckable(True)
        self.btn_dictionary.setCursor(Qt.PointingHandCursor)

        self.mode_group.addButton(self.btn_translate, 0)
        self.mode_group.addButton(self.btn_polish, 1)
        self.mode_group.addButton(self.btn_dictionary, 2)
        self.mode_group.idClicked.connect(self._on_mode_clicked)

        row1.addWidget(self.btn_translate)
        row1.addWidget(self.btn_polish)
        row1.addWidget(self.btn_dictionary)

        # 分割线效果
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #3F3F46;")
        row1.addWidget(sep1)

        # 2. 语言选择（带分隔线、2个记忆槽位与二级级联菜单的语言按钮）
        self.btn_src_lang = LanguageMenuButton(is_src=True, parent=self)

        self.btn_swap = QPushButton("⇄")
        self.btn_swap.setObjectName("secondaryBtn")
        self.btn_swap.setToolTip("互换输入和输出语言")
        self.btn_swap.setFixedWidth(36)
        self.btn_swap.setCursor(Qt.PointingHandCursor)
        self.btn_swap.clicked.connect(self._on_swap_clicked)

        self.btn_target_lang = LanguageMenuButton(is_src=False, parent=self)

        # 恢复上次保存的语言
        last_src = settings.get("last_src_lang", "Auto")
        last_target = settings.get("last_target_lang", "English")
        self.btn_src_lang.set_current_language(last_src, emit_signal=False)
        self.btn_target_lang.set_current_language(last_target, emit_signal=False)

        self.btn_src_lang.language_selected.connect(self._on_lang_changed)
        self.btn_target_lang.language_selected.connect(self._on_lang_changed)

        row1.addWidget(self.btn_src_lang)
        row1.addWidget(self.btn_swap)
        row1.addWidget(self.btn_target_lang)

        # 恢复上次保存的模式状态（确保按钮高亮、语言对禁用逻辑与设置 100% 同步）
        last_mode = settings.get("last_mode", "translate")
        self.set_mode(last_mode, emit_signal=False)

        row1.addStretch()
        main_layout.addLayout(row1)

        # ----------------------------------------------------
        # 第二排：模型服务状态、测速遥测与系统操作 (大幅释放宽度)
        # ----------------------------------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # 3. 模型切换下拉列表
        lbl_model = QLabel("模型:")
        lbl_model.setStyleSheet("color: #A1A1AA;")
        row2.addWidget(lbl_model)

        self.combo_profile = QComboBox()
        self.combo_profile.setMinimumWidth(130)
        self.combo_profile.setCursor(Qt.PointingHandCursor)
        self.reload_profiles()
        self.combo_profile.currentIndexChanged.connect(self._on_profile_changed)
        row2.addWidget(self.combo_profile)

        # 4. API 连接状态与速度指示器（显示延迟与 tok/s）
        self.api_status = ApiStatusIndicator(self)
        self.api_status.refresh_requested.connect(self._check_current_api_status)
        row2.addWidget(self.api_status)

        # 5. 省钱模式快捷切换开关
        self.btn_eco = QPushButton("💰 省钱模式")
        self.btn_eco.setObjectName("secondaryBtn")
        self.btn_eco.setCheckable(True)
        self.btn_eco.setCursor(Qt.PointingHandCursor)
        self.btn_eco.setToolTip("开启后使用极简 Prompt，大幅节省 80%~90% 输入 Token 消耗")
        is_eco = bool(settings.get("eco_mode", False))
        self.btn_eco.setChecked(is_eco)
        self._update_eco_style(is_eco)
        self.btn_eco.toggled.connect(self._on_eco_toggled)
        row2.addWidget(self.btn_eco)

        row2.addStretch()

        # 6. 记忆历史按钮
        self.btn_history = QPushButton("📚 记忆")
        self.btn_history.setObjectName("secondaryBtn")
        self.btn_history.setCursor(Qt.PointingHandCursor)
        self.btn_history.setToolTip("查看翻译、润色与词典历史记忆记录 (快捷键 Ctrl+H)")
        self.btn_history.clicked.connect(self.open_history_requested.emit)
        row2.addWidget(self.btn_history)

        # 7. 主题切换快捷菜单按钮
        self.btn_theme = QPushButton("🎨 主题")
        self.btn_theme.setObjectName("secondaryBtn")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("快速切换应用界面显示主题 (黑色 / 白色 / 跟随系统)")

        self.menu_theme = QMenu(self)
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        self.action_theme_dark = QAction("🌙 黑色主题", self)
        self.action_theme_dark.setCheckable(True)
        self.action_theme_dark.triggered.connect(lambda: self._set_theme("dark"))
        self.theme_action_group.addAction(self.action_theme_dark)
        self.menu_theme.addAction(self.action_theme_dark)

        self.action_theme_light = QAction("☀️ 白色主题", self)
        self.action_theme_light.setCheckable(True)
        self.action_theme_light.triggered.connect(lambda: self._set_theme("light"))
        self.theme_action_group.addAction(self.action_theme_light)
        self.menu_theme.addAction(self.action_theme_light)

        self.action_theme_system = QAction("💻 跟随系统", self)
        self.action_theme_system.setCheckable(True)
        self.action_theme_system.triggered.connect(lambda: self._set_theme("system"))
        self.theme_action_group.addAction(self.action_theme_system)
        self.menu_theme.addAction(self.action_theme_system)

        self.btn_theme.setMenu(self.menu_theme)
        row2.addWidget(self.btn_theme)

        # 8. 设置按钮
        self.btn_settings = QPushButton("⚙ 设置")
        self.btn_settings.setObjectName("secondaryBtn")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings_requested.emit)
        row2.addWidget(self.btn_settings)

        main_layout.addLayout(row2)

        # 连接主题管理器信号并初始化按钮状态
        theme_mgr = ThemeManager.get_instance()
        theme_mgr.theme_changed.connect(self._on_theme_changed)
        self._sync_theme_ui(theme_mgr.get_mode(), theme_mgr.is_dark())

        # 启动后异步自动进行初次网络连通性检测
        self._check_current_api_status()

    def reload_profiles(self):
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        profiles = settings.get("profiles", [])
        active_id = settings.get("active_profile_id", "")

        active_index = 0
        for idx, p in enumerate(profiles):
            self.combo_profile.addItem(p.get("name", "Unnamed"), p.get("id"))
            if p.get("id") == active_id:
                active_index = idx

        if self.combo_profile.count() > 0:
            self.combo_profile.setCurrentIndex(active_index)
        self.combo_profile.blockSignals(False)

    def set_mode(self, mode: str, emit_signal: bool = True):
        mode_map = {"translate": 0, "polish": 1, "dictionary": 2}
        if mode not in mode_map:
            mode = "translate"
        btn_id = mode_map[mode]

        btn = self.mode_group.button(btn_id)
        if btn:
            self.mode_group.blockSignals(True)
            btn.setChecked(True)
            self.mode_group.blockSignals(False)

        if mode == "polish":
            self.btn_swap.setEnabled(False)
            self.btn_target_lang.setEnabled(False)
            self.btn_target_lang.setToolTip("润色模式自动保持原语言，不进行跨语言翻译")
        else:
            self.btn_swap.setEnabled(True)
            self.btn_target_lang.setEnabled(True)
            self.btn_target_lang.setToolTip("")

        settings.set("last_mode", mode)

        if emit_signal:
            self.mode_changed.emit(mode)

    def _on_mode_clicked(self, btn_id: int):
        mode_map = {0: "translate", 1: "polish", 2: "dictionary"}
        mode = mode_map.get(btn_id, "translate")
        self.set_mode(mode, emit_signal=True)

    def _on_lang_changed(self, _code=None):
        src = self.btn_src_lang.get_current_code()
        target = self.btn_target_lang.get_current_code()
        settings.set("last_src_lang", src)
        settings.set("last_target_lang", target)
        self.languages_changed.emit(src, target)

    def _on_swap_clicked(self):
        self.swap_requested.emit()

    def set_languages(self, src: str, target: str):
        self.btn_src_lang.set_current_language(src, emit_signal=False)
        self.btn_target_lang.set_current_language(target, emit_signal=False)
        self._on_lang_changed()

    def _on_profile_changed(self):
        profile_id = self.combo_profile.currentData()
        if profile_id:
            settings.set_active_profile_id(profile_id)
            self.profile_changed.emit(profile_id)
            self._check_current_api_status()

    def _check_current_api_status(self):
        profile = settings.get_active_profile()
        base_url = profile.get("base_url", "")
        api_key = profile.get("api_key", "")
        self.api_status.check_connection(base_url, api_key)

    def get_current_mode(self) -> str:
        btn_id = self.mode_group.checkedId()
        mode_map = {0: "translate", 1: "polish", 2: "dictionary"}
        return mode_map.get(btn_id, "translate")

    def get_current_profile(self) -> dict:
        return settings.get_active_profile()

    def get_languages(self) -> tuple[str, str]:
        return self.btn_src_lang.get_current_code(), self.btn_target_lang.get_current_code()

    def _update_eco_style(self, checked: bool):
        self.btn_eco.setText("💰 省钱模式")
        if checked:
            is_dark = ThemeManager.get_instance().is_dark()
            if is_dark:
                self.btn_eco.setStyleSheet(
                    "QPushButton#secondaryBtn {"
                    "  background-color: #064e3b;"
                    "  color: #34d399;"
                    "  border: 1px solid #059669;"
                    "  border-radius: 6px;"
                    "  padding: 6px 12px;"
                    "  font-size: 12px;"
                    "}"
                    "QPushButton#secondaryBtn:hover {"
                    "  background-color: #047857;"
                    "  color: #a7f3d0;"
                    "  border-color: #10b981;"
                    "}"
                )
            else:
                self.btn_eco.setStyleSheet(
                    "QPushButton#secondaryBtn {"
                    "  background-color: #D1FAE5;"
                    "  color: #065F46;"
                    "  border: 1px solid #10B981;"
                    "  border-radius: 6px;"
                    "  padding: 6px 12px;"
                    "  font-size: 12px;"
                    "}"
                    "QPushButton#secondaryBtn:hover {"
                    "  background-color: #A7F3D0;"
                    "  color: #064E3B;"
                    "  border-color: #059669;"
                    "}"
                )
            self.btn_eco.setToolTip("【省钱模式：已开启】点击关闭省钱模式，恢复完整专家提示词")
        else:
            self.btn_eco.setStyleSheet("")
            self.btn_eco.setToolTip("【省钱模式：已关闭】点击开启极简 Prompt 省钱模式，节省 80%~90% Token")

    def _on_eco_toggled(self, checked: bool):
        settings.set("eco_mode", checked)
        self._update_eco_style(checked)
        self.eco_mode_changed.emit(checked)

    def sync_eco_mode(self):
        is_eco = bool(settings.get("eco_mode", False))
        self.btn_eco.blockSignals(True)
        self.btn_eco.setChecked(is_eco)
        self._update_eco_style(is_eco)
        self.btn_eco.blockSignals(False)

    def _set_theme(self, mode: str):
        ThemeManager.get_instance().apply_theme(mode)

    def _on_theme_changed(self, mode: str, is_dark: bool):
        self._sync_theme_ui(mode, is_dark)
        self._update_eco_style(self.btn_eco.isChecked())

    def _sync_theme_ui(self, mode: str, is_dark: bool):
        self.theme_action_group.blockSignals(True)
        if mode == "dark":
            self.action_theme_dark.setChecked(True)
            self.btn_theme.setText("🎨 黑色")
            self.btn_theme.setToolTip("当前主题: 🌙 黑色 (点击切换)")
        elif mode == "light":
            self.action_theme_light.setChecked(True)
            self.btn_theme.setText("🎨 白色")
            self.btn_theme.setToolTip("当前主题: ☀️ 白色 (点击切换)")
        elif mode == "system":
            self.action_theme_system.setChecked(True)
            status_text = "深色" if is_dark else "浅色"
            self.btn_theme.setText(f"🎨 系统 ({status_text})")
            self.btn_theme.setToolTip(f"当前主题: 💻 跟随系统 [当前OS: {status_text}] (点击切换)")
        self.theme_action_group.blockSignals(False)

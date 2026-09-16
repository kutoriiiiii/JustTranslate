# -*- coding: utf-8 -*-
"""Settings modal dialog with thinking mode, protocol, and scene scheduling controls."""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton, 
    QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout, QMessageBox,
    QCheckBox, QFrame, QScrollArea, QApplication
)
from PySide6.QtGui import QPixmap, QIcon, QWheelEvent
from PySide6.QtCore import Signal, QThread, Qt, QEvent, QObject, QPointF
from config.settings import (
    settings, DEFAULT_PROFILES, 
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_DESCRIPTION
)
from config.default_prompts import DEFAULT_PROMPTS
from core.history_manager import history_manager
from core.theme_manager import ThemeManager
from core.llm_client import LLMClient
from core.capability_registry import CapabilityRegistry, ProbeState
from ui.components.model_probe_dialog import ModelProbeDialog
from ui.components.wheel_filter import (
    NoWheelComboBox, NoWheelSpinBox, NoWheelDoubleSpinBox, 
    NoWheelEventFilter, forward_wheel_to_scroll, _forward_wheel_to_scroll
)




class TestConnectionWorker(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, base_url: str, api_key: str, model: str, protocol: str = "openai_chat"):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.protocol = protocol

    def run(self):
        client = LLMClient(self.base_url, self.api_key, self.model, timeout=30.0, protocol=self.protocol)
        success, msg = client.test_connection()
        self.result_signal.emit(success, msg)


class ProbeModelsWorker(QThread):
    result_signal = Signal(bool, list, str)

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        client = LLMClient(self.base_url, self.api_key, timeout=30.0)
        success, models, msg = client.list_models()
        self.result_signal.emit(success, models, msg)


class ProbeReasoningWorker(QThread):
    result_signal = Signal(str, str, str)  # (state, control_kind, details)

    def __init__(self, base_url: str, api_key: str, model: str, protocol: str = "openai_chat"):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.protocol = protocol

    def run(self):
        client = LLMClient(self.base_url, self.api_key, self.model, timeout=15.0, protocol=self.protocol)
        res = client.probe_reasoning_capability(timeout=15.0)
        self.result_signal.emit(res.state.value, res.control_kind.value, res.details)


class SettingsDialog(QDialog):
    """Settings modal dialog."""
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置与模型配置 - Just Translate")
        self.setMinimumSize(650, 560)
        self.test_worker = None
        self.probe_worker = None
        self.reasoning_probe_worker = None
        self._wheel_filter = NoWheelEventFilter(self)
        self._init_ui()
        self._load_data()

    @staticmethod
    def _wrap_scroll(widget: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(widget)
        return sa

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget()

        # --------------------------------------------------------------------
        # Tab 1: 模型服务配置
        # --------------------------------------------------------------------
        tab_models = QWidget()
        layout_models = QVBoxLayout(tab_models)
        layout_models.setSpacing(10)

        # Profile 切换与新建/删除栏
        profile_bar = QHBoxLayout()
        profile_bar.addWidget(QLabel("选择/切换配置:"))
        self.combo_profiles = NoWheelComboBox()
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_selected)
        profile_bar.addWidget(self.combo_profiles, 1)

        self.btn_add_profile = QPushButton("➕ 新建")
        self.btn_add_profile.setObjectName("secondaryBtn")
        self.btn_add_profile.clicked.connect(self._add_profile)
        profile_bar.addWidget(self.btn_add_profile)

        self.btn_del_profile = QPushButton("🗑 删除")
        self.btn_del_profile.setObjectName("secondaryBtn")
        self.btn_del_profile.clicked.connect(self._del_profile)
        profile_bar.addWidget(self.btn_del_profile)

        layout_models.addLayout(profile_bar)

        # 详细表单
        form_layout = QFormLayout()
        form_layout.setSpacing(8)

        self.edit_name = QLineEdit()
        form_layout.addRow("配置名称:", self.edit_name)

        # 协议类型
        self.combo_protocol = NoWheelComboBox()
        self.combo_protocol.addItem("OpenAI Chat Completions (标准/通用)", "openai_chat")
        self.combo_protocol.addItem("OpenAI Responses API (/v1/responses)", "openai_responses")
        self.combo_protocol.addItem("Anthropic Messages API (/v1/messages)", "anthropic_messages")
        self.combo_protocol.addItem("Google Gemini Generate Content API", "gemini_content")
        self.combo_protocol.addItem("Ollama 原生 API (/api/chat)", "ollama_native")
        self.combo_protocol.addItem("vLLM OpenAI-compatible (模板控制)", "vllm_chat")
        self.combo_protocol.addItem("通用兼容 (普通模式，不注入非标准参数)", "generic_openai")
        self.combo_protocol.currentIndexChanged.connect(self._on_protocol_changed)
        form_layout.addRow("API 协议类型:", self.combo_protocol)

        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText("如 http://127.0.0.1:8080/v1 或 https://api.deepseek.com/v1")
        self.edit_base_url.textChanged.connect(self._on_endpoint_or_model_edited)
        form_layout.addRow("Base URL:", self.edit_base_url)

        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.edit_api_key.setPlaceholderText("本地模型可留空或填 sk-no-key")
        form_layout.addRow("API Key:", self.edit_api_key)

        model_layout = QHBoxLayout()
        self.edit_model = QLineEdit()
        self.edit_model.setPlaceholderText("如 default, qwen2.5:7b, gpt-4o-mini 等")
        self.edit_model.textChanged.connect(self._on_endpoint_or_model_edited)
        model_layout.addWidget(self.edit_model, 1)

        self.btn_probe = QPushButton("📡 探测模型")
        self.btn_probe.setObjectName("secondaryBtn")
        self.btn_probe.setToolTip("向当前 Base URL 发送请求，探测并自选/批量导入可用模型")
        self.btn_probe.clicked.connect(self._probe_models)
        model_layout.addWidget(self.btn_probe)

        form_layout.addRow("模型名称:", model_layout)

        # 思考能力探测按钮与指示
        reasoning_probe_layout = QHBoxLayout()
        self.btn_probe_reasoning = QPushButton("⚡ 探测思考能力")
        self.btn_probe_reasoning.setObjectName("secondaryBtn")
        self.btn_probe_reasoning.setToolTip("向当前端点发送合规微型探针，检测是否支持思考模式或关闭思考")
        self.btn_probe_reasoning.clicked.connect(self._probe_reasoning_capability)
        reasoning_probe_layout.addWidget(self.btn_probe_reasoning)

        self.lbl_probe_reasoning_status = QLabel("未探测")
        self.lbl_probe_reasoning_status.setStyleSheet("color: #71717A; font-size: 12px;")
        reasoning_probe_layout.addWidget(self.lbl_probe_reasoning_status, 1)
        form_layout.addRow("思考能力状态:", reasoning_probe_layout)

        # 思考模式覆盖逃生口
        self.combo_reasoning_override = NoWheelComboBox()
        self.combo_reasoning_override.addItem("自动检测 (遵循官方注册表与探测结果)", "auto")
        self.combo_reasoning_override.addItem("强制开启思考模式", "force_on")
        self.combo_reasoning_override.addItem("强制关闭思考模式", "force_off")
        self.combo_reasoning_override.addItem("不干涉思考模式 (原生透传，不注入任何控制参数)", "passthrough")
        self.combo_reasoning_override.addItem("禁用思考参数 (强制普通文本兼容)", "unsupported")
        form_layout.addRow("思考模式覆盖 (逃生口):", self.combo_reasoning_override)

        self.edit_ocr_model = QLineEdit()
        self.edit_ocr_model.setPlaceholderText("选填，如 GLM-OCR、gpt-4o-mini、qwen-vl；留空则视为主模型")
        form_layout.addRow("OCR 识图模型 (选填):", self.edit_ocr_model)

        self.spin_temp = NoWheelDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.1)
        self.spin_temp.setValue(settings.get("temperature", 0.3))
        form_layout.addRow("采样温度 (Temperature):", self.spin_temp)

        layout_models.addLayout(form_layout)

        # 测试连接栏
        test_bar = QHBoxLayout()
        self.btn_test = QPushButton("🔍 测试连接 (30秒超时)")
        self.btn_test.setObjectName("secondaryBtn")
        self.btn_test.clicked.connect(self._test_connection)
        test_bar.addWidget(self.btn_test)

        self.lbl_test_result = QLabel("")
        test_bar.addWidget(self.lbl_test_result, 1)
        layout_models.addLayout(test_bar)

        layout_models.addStretch()
        self.tabs.addTab(self._wrap_scroll(tab_models), "模型服务")

        # --------------------------------------------------------------------
        # Tab 2: 思考模式与场景调度
        # --------------------------------------------------------------------
        tab_reasoning = QWidget()
        layout_reasoning = QVBoxLayout(tab_reasoning)
        layout_reasoning.setSpacing(12)

        form_reasoning = QFormLayout()
        form_reasoning.setSpacing(10)

        self.combo_reasoning_mode = NoWheelComboBox()
        self.combo_reasoning_mode.addItem("智能自动调度 (推荐：根据功能场景与模型能力自适应)", "auto")
        self.combo_reasoning_mode.addItem("全局强制开启 (所有未覆盖场景默认深度思考)", "always_on")
        self.combo_reasoning_mode.addItem("全局强制关闭 (所有未覆盖场景默认关闭思考)", "always_off")
        self.combo_reasoning_mode.addItem("全局不干涉 (原生透传，不注入任何控制参数)", "passthrough")
        form_reasoning.addRow("全局思考模式总开关:", self.combo_reasoning_mode)

        self.combo_reasoning_effort = NoWheelComboBox()
        self.combo_reasoning_effort.addItem("低强度 (Low / 快速思考)", "low")
        self.combo_reasoning_effort.addItem("中等强度 (Medium / 平衡推荐)", "medium")
        self.combo_reasoning_effort.addItem("高强度 (High / 深度推演)", "high")
        self.combo_reasoning_effort.addItem("自适应动态 (Dynamic / 模型自主决策)", "dynamic")
        form_reasoning.addRow("全局思考强度等级:", self.combo_reasoning_effort)

        fast_threshold_box = QHBoxLayout()
        self.spin_fast_chars = NoWheelSpinBox()
        self.spin_fast_chars.setRange(0, 1000)
        self.spin_fast_chars.setValue(settings.get("fast_translate_threshold_chars", 150))
        self.spin_fast_chars.setToolTip("字符数少于此值且句数满足条件时判定为快翻短句；设为 0 完全停用快翻自动判定")
        fast_threshold_box.addWidget(QLabel("字符数少于:"))
        fast_threshold_box.addWidget(self.spin_fast_chars)

        self.spin_fast_sentences = NoWheelSpinBox()
        self.spin_fast_sentences.setRange(1, 10)
        self.spin_fast_sentences.setValue(settings.get("fast_translate_threshold_sentences", 2))
        fast_threshold_box.addWidget(QLabel("且断句少于等于:"))
        fast_threshold_box.addWidget(self.spin_fast_sentences)
        fast_threshold_box.addWidget(QLabel("句"))
        fast_threshold_box.addStretch()
        form_reasoning.addRow("短句快翻判定标准:", fast_threshold_box)

        layout_reasoning.addLayout(form_reasoning)

        # 子功能独立开关
        layout_reasoning.addWidget(QLabel("<b>子功能独立控制（优先级高于全局总开关，分 3 级继承）：</b>"))

        form_overrides = QFormLayout()
        form_overrides.setSpacing(8)

        def make_override_combo():
            c = NoWheelComboBox()
            c.addItem("跟随全局设置 (继承)", "inherit")
            c.addItem("强制关闭思考模式 (推荐秒出)", "off")
            c.addItem("强制开启深度思考", "on")
            c.addItem("不干涉思考模式 (原生透传)", "passthrough")
            c.installEventFilter(self._wheel_filter)
            return c

        self.combo_override_dict = make_override_combo()
        form_overrides.addRow("📖 词典查询模式:", self.combo_override_dict)

        self.combo_override_ocr = make_override_combo()
        form_overrides.addRow("🖼️ OCR 识图翻译:", self.combo_override_ocr)

        self.combo_override_fast = make_override_combo()
        form_overrides.addRow("⚡ 快速短句翻译:", self.combo_override_fast)

        self.combo_override_deep = make_override_combo()
        form_overrides.addRow("📚 长篇深度翻译:", self.combo_override_deep)

        self.combo_override_polish = make_override_combo()
        form_overrides.addRow("✨ 文本深度润色:", self.combo_override_polish)

        layout_reasoning.addLayout(form_overrides)
        layout_reasoning.addStretch()
        self.tabs.addTab(self._wrap_scroll(tab_reasoning), "思考与调度")

        # --------------------------------------------------------------------
        # Tab 3: 自定义系统提示词
        # --------------------------------------------------------------------
        tab_prompts = QWidget()
        layout_prompts = QVBoxLayout(tab_prompts)
        layout_prompts.setSpacing(8)

        prompt_mode_bar = QHBoxLayout()
        prompt_mode_bar.addWidget(QLabel("选择模式:"))
        self.combo_prompt_mode = NoWheelComboBox()
        self.combo_prompt_mode.addItem("翻译 (translate)", "translate")
        self.combo_prompt_mode.addItem("润色 (polish)", "polish")
        self.combo_prompt_mode.addItem("词典 (dictionary)", "dictionary")
        self.combo_prompt_mode.currentIndexChanged.connect(self._on_prompt_mode_changed)
        prompt_mode_bar.addWidget(self.combo_prompt_mode, 1)

        self.btn_reset_prompt = QPushButton("↺ 恢复此模式默认提示词")
        self.btn_reset_prompt.setObjectName("secondaryBtn")
        self.btn_reset_prompt.clicked.connect(self._reset_current_prompt)
        prompt_mode_bar.addWidget(self.btn_reset_prompt)

        layout_prompts.addLayout(prompt_mode_bar)

        layout_prompts.addWidget(QLabel("自定义系统提示词 (留空则自动应用内建专家提示词):"))
        self.edit_prompt = QTextEdit()
        layout_prompts.addWidget(self.edit_prompt)

        self.tabs.addTab(tab_prompts, "提示词定制")

        # --------------------------------------------------------------------
        # Tab 4: 常规与记忆管理
        # --------------------------------------------------------------------
        tab_general = QWidget()
        layout_general = QVBoxLayout(tab_general)
        layout_general.setSpacing(12)

        form_general = QFormLayout()
        form_general.setSpacing(10)

        # 界面显示主题
        self.combo_theme = NoWheelComboBox()
        self.combo_theme.addItem("🌙 黑色主题", "dark")
        self.combo_theme.addItem("☀️ 白色主题", "light")
        self.combo_theme.addItem("💻 跟随系统", "system")
        form_general.addRow("界面显示主题:", self.combo_theme)

        # 默认输出格式
        self.combo_format = NoWheelComboBox()
        self.combo_format.addItem("📝 Markdown 格式 (支持标题、列表与富文本)", "markdown")
        self.combo_format.addItem("📄 纯文本格式 (Plain Text 无排版标记)", "plain")
        form_general.addRow("默认文本输出格式:", self.combo_format)

        # 记忆容量
        self.combo_history_limit = NoWheelComboBox()
        self.combo_history_limit.addItem("50 条", 50)
        self.combo_history_limit.addItem("100 条 (推荐默认)", 100)
        self.combo_history_limit.addItem("500 条", 500)
        form_general.addRow("记忆历史保留条数:", self.combo_history_limit)

        # 最小化托盘
        self.check_minimize_tray = QCheckBox("点击窗口关闭按钮时最小化到系统托盘（后台常驻）")
        form_general.addRow("系统托盘行为:", self.check_minimize_tray)

        # 省钱模式
        self.check_eco_mode = QCheckBox("启用省钱模式 (使用极简提示词，节省 80% 以上 Prompt 输入 Token)")
        form_general.addRow("省钱模式 (Eco):", self.check_eco_mode)

        layout_general.addLayout(form_general)

        # 记忆数据库统计与清理
        layout_general.addWidget(QLabel("<b>记忆存储管理 (SQLite 单文件持久化):</b>"))
        self.lbl_history_stats = QLabel("当前记忆库已保存 0 条记录")
        self.lbl_history_stats.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        layout_general.addWidget(self.lbl_history_stats)

        btn_clear_box = QHBoxLayout()
        self.btn_clear_history = QPushButton("🗑 清空历史记忆数据库")
        self.btn_clear_history.setObjectName("dangerBtn")
        self.btn_clear_history.clicked.connect(self._clear_history_from_settings)
        btn_clear_box.addWidget(self.btn_clear_history)
        btn_clear_box.addStretch()
        layout_general.addLayout(btn_clear_box)

        layout_general.addStretch()
        self.tabs.addTab(self._wrap_scroll(tab_general), "常规与记忆")

        # --------------------------------------------------------------------
        # Tab 5: 关于
        # --------------------------------------------------------------------
        tab_about = QWidget()
        layout_about = QVBoxLayout(tab_about)
        layout_about.setContentsMargins(24, 20, 24, 20)
        layout_about.setSpacing(16)

        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        header_layout.setSpacing(8)

        lbl_about_icon = QLabel()
        lbl_about_icon.setAlignment(Qt.AlignCenter)
        icon_path = self._resolve_icon_path()
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                lbl_about_icon.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_layout.addWidget(lbl_about_icon)

        lbl_about_title = QLabel(APP_NAME)
        lbl_about_title.setObjectName("aboutTitle")
        lbl_about_title.setAlignment(Qt.AlignCenter)
        lbl_about_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(lbl_about_title)

        lbl_about_version = QLabel(APP_VERSION)
        lbl_about_version.setAlignment(Qt.AlignCenter)
        lbl_about_version.setStyleSheet("color: #71717A; font-size: 13px;")
        header_layout.addWidget(lbl_about_version)

        lbl_about_author = QLabel(APP_AUTHOR)
        lbl_about_author.setAlignment(Qt.AlignCenter)
        lbl_about_author.setStyleSheet("color: #71717A; font-size: 12px;")
        header_layout.addWidget(lbl_about_author)

        lbl_about_desc = QLabel(APP_DESCRIPTION)
        lbl_about_desc.setAlignment(Qt.AlignCenter)
        lbl_about_desc.setWordWrap(True)
        lbl_about_desc.setStyleSheet("color: #A1A1AA; font-size: 13px; line-height: 1.4;")
        header_layout.addWidget(lbl_about_desc)

        layout_about.addLayout(header_layout)
        layout_about.addStretch()
        self.tabs.addTab(self._wrap_scroll(tab_about), "关于")

        main_layout.addWidget(self.tabs)

        # 底部确定/取消栏
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        self.btn_save = QPushButton("💾 保存全部设置")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._save_all)
        bottom_bar.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(self.btn_cancel)

        main_layout.addLayout(bottom_bar)

        # 完全解绑所有下拉菜单与微调框的鼠标滚轮，防止误触改变选项，并确保滚轮平滑滚动整页
        for cb in self.findChildren(QComboBox):
            cb.installEventFilter(self._wheel_filter)
        for sb in self.findChildren(QSpinBox):
            sb.installEventFilter(self._wheel_filter)
        for dsb in self.findChildren(QDoubleSpinBox):
            dsb.installEventFilter(self._wheel_filter)

    def _resolve_icon_path(self) -> Path:
        base_dir = Path(__file__).resolve().parent.parent.parent
        p = base_dir / "resources" / "icon.png"
        if not p.exists():
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                p_mei = Path(meipass) / "resources" / "icon.png"
                if p_mei.exists():
                    return p_mei
            exe_dir = Path(sys.executable).resolve().parent
            p_exe = exe_dir / "resources" / "icon.png"
            if p_exe.exists():
                return p_exe
            p_internal = exe_dir / "_internal" / "resources" / "icon.png"
            if p_internal.exists():
                return p_internal
        return p

    def _load_data(self):
        # 载入 profiles
        self.profiles = [dict(p) for p in settings.get("profiles", DEFAULT_PROFILES)]
        self.active_id = settings.get("active_profile_id", "llama_cpp")

        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        selected_idx = 0
        for idx, p in enumerate(self.profiles):
            self.combo_profiles.addItem(p.get("name", "Unnamed"), p.get("id"))
            if p.get("id") == self.active_id:
                selected_idx = idx
        self.combo_profiles.setCurrentIndex(selected_idx)
        self.combo_profiles.blockSignals(False)

        self._load_current_profile_form()

        # 载入思考与场景调度设置
        r_mode = settings.get("reasoning_mode", "auto")
        r_mode_idx = {"auto": 0, "always_on": 1, "always_off": 2, "passthrough": 3}.get(r_mode, 0)
        self.combo_reasoning_mode.setCurrentIndex(r_mode_idx)

        r_effort = settings.get("reasoning_effort", "medium")
        r_effort_idx = {"low": 0, "medium": 1, "high": 2, "dynamic": 3}.get(r_effort, 1)
        self.combo_reasoning_effort.setCurrentIndex(r_effort_idx)

        self.spin_fast_chars.setValue(int(settings.get("fast_translate_threshold_chars", 150)))
        self.spin_fast_sentences.setValue(int(settings.get("fast_translate_threshold_sentences", 2)))

        overrides = settings.get("feature_reasoning_overrides", {})
        def set_override(combo, key, default):
            v = overrides.get(key, default)
            idx = {"inherit": 0, "off": 1, "on": 2, "passthrough": 3}.get(v, 0)
            combo.setCurrentIndex(idx)

        set_override(self.combo_override_dict, "dictionary", "off")
        set_override(self.combo_override_ocr, "ocr", "off")
        set_override(self.combo_override_fast, "fast_translate", "off")
        set_override(self.combo_override_deep, "deep_translate", "inherit")
        set_override(self.combo_override_polish, "polish", "on")

        # 载入 Prompt
        self.custom_prompts = dict(settings.get("custom_prompts", {}))
        self._on_prompt_mode_changed()

        # 载入常规与记忆设置
        current_theme = settings.get("app_theme", "dark")
        theme_idx = {"dark": 0, "light": 1, "system": 2}.get(current_theme, 0)
        self.combo_theme.setCurrentIndex(theme_idx)

        output_fmt = settings.get("output_format", "markdown")
        self.combo_format.setCurrentIndex(1 if output_fmt == "plain" else 0)

        hist_limit = int(settings.get("history_limit", 100))
        limit_idx = {50: 0, 100: 1, 500: 2}.get(hist_limit, 1)
        self.combo_history_limit.setCurrentIndex(limit_idx)

        self.check_minimize_tray.setChecked(settings.get("minimize_to_tray_on_close", True))
        self.check_eco_mode.setChecked(bool(settings.get("eco_mode", False)))
        self._refresh_history_stats()

    def _refresh_history_stats(self):
        count = history_manager.get_count()
        limit = int(settings.get("history_limit", 100))
        self.lbl_history_stats.setText(f"当前记忆库已保存 {count} / {limit} 条记录 (单文件: {history_manager.db_path})")

    def _clear_history_from_settings(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史记忆数据吗？此操作将彻底删除数据库中的全部历史条目。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            history_manager.clear_all()
            self._refresh_history_stats()
            QMessageBox.information(self, "提示", "历史记忆数据库已清空！")

    def _load_current_profile_form(self):
        idx = self.combo_profiles.currentIndex()
        if 0 <= idx < len(self.profiles):
            p = self.profiles[idx]
            self.edit_name.setText(p.get("name", ""))
            self.edit_base_url.setText(p.get("base_url", ""))
            self.edit_api_key.setText(p.get("api_key", ""))
            self.edit_model.setText(p.get("model", ""))
            self.edit_ocr_model.setText(p.get("ocr_model", ""))

            # 载入协议类型
            proto = p.get("protocol", "openai_chat")
            for i in range(self.combo_protocol.count()):
                if self.combo_protocol.itemData(i) == proto:
                    self.combo_protocol.setCurrentIndex(i)
                    break

            # 载入思考覆盖
            override = p.get("reasoning_override", "auto")
            for i in range(self.combo_reasoning_override.count()):
                if self.combo_reasoning_override.itemData(i) == override:
                    self.combo_reasoning_override.setCurrentIndex(i)
                    break

            self._update_probe_status_display(p.get("base_url", ""), proto, p.get("model", ""))

    def _save_current_form_to_profile(self):
        idx = self.combo_profiles.currentIndex()
        if 0 <= idx < len(self.profiles):
            self.profiles[idx]["name"] = self.edit_name.text().strip()
            self.profiles[idx]["protocol"] = self.combo_protocol.currentData()
            self.profiles[idx]["base_url"] = self.edit_base_url.text().strip()
            self.profiles[idx]["api_key"] = self.edit_api_key.text().strip()
            self.profiles[idx]["model"] = self.edit_model.text().strip()
            self.profiles[idx]["reasoning_override"] = self.combo_reasoning_override.currentData()
            self.profiles[idx]["ocr_model"] = self.edit_ocr_model.text().strip()
            self.combo_profiles.setItemText(idx, self.profiles[idx]["name"])

    def _on_endpoint_or_model_edited(self):
        base_url = self.edit_base_url.text().strip()
        protocol = self.combo_protocol.currentData()
        model = self.edit_model.text().strip()
        self._update_probe_status_display(base_url, protocol, model)

    def _on_protocol_changed(self):
        self._on_endpoint_or_model_edited()

    def _update_probe_status_display(self, base_url: str, protocol: str, model: str):
        if not base_url or not model:
            self.lbl_probe_reasoning_status.setText("<span style='color:#71717A;'>未配置</span>")
            return

        cached = CapabilityRegistry.get_instance().get_probe_cache(base_url, protocol, model)
        if cached:
            state_labels = {
                ProbeState.CONFIRMED_SUPPORTED: ("<span style='color:#10B981;'>✅ 已证实支持思考</span>", "该端点已通过探针验证"),
                ProbeState.ACCEPTED_BUT_UNVERIFIED: ("<span style='color:#3B82F6;'>ℹ️ 参数已接受 (待验证)</span>", "HTTP 200 已接受参数"),
                ProbeState.REJECTED_PARAMETER: ("<span style='color:#EF4444;'>❌ 拒绝思考参数 (普通模式)</span>", "服务端返回 400 拒绝思考参数"),
                ProbeState.FORCED_ON: ("<span style='color:#F59E0B;'>🔒 强制深度思考 (不可关闭)</span>", "纯推理专用模型"),
                ProbeState.UNSUPPORTED: ("<span style='color:#71717A;'>⚪ 普通文本模式</span>", "不支持思考参数"),
            }
            text, tip = state_labels.get(cached.probe_state, ("未知状态", ""))
            self.lbl_probe_reasoning_status.setText(text)
            self.lbl_probe_reasoning_status.setToolTip(f"{tip}\n{cached.details}")
        else:
            reg = CapabilityRegistry.get_instance().match(provider="", protocol=protocol, model=model)
            if reg:
                self.lbl_probe_reasoning_status.setText(f"<span style='color:#A1A1AA;'>官方规范: {reg.model_family}</span>")
                self.lbl_probe_reasoning_status.setToolTip(f"官方已知规范，控制方式: {reg.control_kind.value}")
            else:
                self.lbl_probe_reasoning_status.setText("<span style='color:#71717A;'>未探测 (默认普通模式)</span>")
                self.lbl_probe_reasoning_status.setToolTip("未知模型默认不注入非标准思考参数")

    def _on_profile_selected(self, index: int):
        self._load_current_profile_form()
        self.lbl_test_result.setText("")

    def _add_profile(self):
        new_id = f"custom_{len(self.profiles) + 1}"
        new_p = {
            "id": new_id,
            "name": f"自定义配置 {len(self.profiles) + 1}",
            "protocol": "openai_chat",
            "base_url": "http://127.0.0.1:8080/v1",
            "api_key": "",
            "model": "default",
            "reasoning_override": "auto"
        }
        self.profiles.append(new_p)
        self.combo_profiles.addItem(new_p["name"], new_id)
        self.combo_profiles.setCurrentIndex(len(self.profiles) - 1)

    def _del_profile(self):
        if len(self.profiles) <= 1:
            QMessageBox.warning(self, "警告", "必须保留至少一个模型配置！")
            return
        idx = self.combo_profiles.currentIndex()
        del self.profiles[idx]
        self.combo_profiles.removeItem(idx)

    def _test_connection(self):
        self._save_current_form_to_profile()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()
        model = self.edit_model.text().strip()
        protocol = self.combo_protocol.currentData()

        if not base_url:
            self.lbl_test_result.setText("<span style='color:#EF4444;'>Base URL 不能为空</span>")
            return

        self.btn_test.setEnabled(False)
        self.lbl_test_result.setText("⏳ 正在测试连接 (最大等待 30 秒)...")

        self.test_worker = TestConnectionWorker(base_url, api_key, model, protocol=protocol)
        self.test_worker.result_signal.connect(self._on_test_finished)
        self.test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_result.setText(f"<span style='color:#10B981;'>✓ {message}</span>")
        else:
            self.lbl_test_result.setText(f"<span style='color:#EF4444;'>✗ {message}</span>")

    def _probe_reasoning_capability(self):
        self._save_current_form_to_profile()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()
        model = self.edit_model.text().strip()
        protocol = self.combo_protocol.currentData()

        if not base_url or not model:
            QMessageBox.warning(self, "提示", "请先填入有效的 Base URL 和模型名称后再进行探测！")
            return

        self.btn_probe_reasoning.setEnabled(False)
        self.lbl_probe_reasoning_status.setText("⏳ 正在向端点发送合规探针...")

        self.reasoning_probe_worker = ProbeReasoningWorker(base_url, api_key, model, protocol=protocol)
        self.reasoning_probe_worker.result_signal.connect(self._on_reasoning_probe_finished)
        self.reasoning_probe_worker.start()

    def _on_reasoning_probe_finished(self, state_str: str, control_kind_str: str, details: str):
        self.btn_probe_reasoning.setEnabled(True)
        base_url = self.edit_base_url.text().strip()
        protocol = self.combo_protocol.currentData()
        model = self.edit_model.text().strip()
        self._update_probe_status_display(base_url, protocol, model)

        title_map = {
            "confirmed_supported": "探测结论：已证实支持思考模式",
            "accepted_but_unverified": "探测结论：参数已被服务端接受",
            "rejected_parameter": "探测结论：服务端明确拒绝思考参数",
            "forced_on": "探测结论：该模型为强制思考模型",
            "unsupported": "探测结论：不支持思考模式",
            "unavailable_auth_quota": "探测提示：鉴权或网络异常",
        }
        title = title_map.get(state_str, "思考能力探测结果")
        QMessageBox.information(
            self,
            title,
            f"【探测结论状态】：{state_str}\n【控制协议机制】：{control_kind_str}\n\n【详细说明】：\n{details}"
        )

    def _probe_models(self):
        self._save_current_form_to_profile()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先在上方输入有效的 Base URL 服务地址！")
            return

        self.btn_probe.setEnabled(False)
        self.btn_probe.setText("📡 探测中...")

        self.probe_worker = ProbeModelsWorker(base_url, api_key)
        self.probe_worker.result_signal.connect(self._on_probe_finished)
        self.probe_worker.start()

    def _on_probe_finished(self, success: bool, models: list, message: str):
        self.btn_probe.setEnabled(True)
        self.btn_probe.setText("📡 探测模型")

        if not success or not models:
            QMessageBox.warning(self, "探测失败", f"未能成功探测到可用模型列表：\n{message}")
            return

        current_model = self.edit_model.text().strip()
        dialog = ModelProbeDialog(models, current_model=current_model, parent=self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.action == ModelProbeDialog.ACTION_APPLY_CURRENT:
                if dialog.chosen_model:
                    self.edit_model.setText(dialog.chosen_model)
                    self._save_current_form_to_profile()
                    QMessageBox.information(self, "已应用", f"已将模型【{dialog.chosen_model}】填入当前配置。")
            elif dialog.action == ModelProbeDialog.ACTION_BATCH_IMPORT:
                if dialog.chosen_models_batch:
                    base_name = self.edit_name.text().strip() or "模型"
                    base_url = self.edit_base_url.text().strip()
                    api_key = self.edit_api_key.text().strip()
                    protocol = self.combo_protocol.currentData()
                    imported_count = 0

                    for m in dialog.chosen_models_batch:
                        exists = any(p.get("base_url") == base_url and p.get("model") == m for p in self.profiles)
                        if exists:
                            continue
                        new_id = f"imported_{len(self.profiles) + 1}"
                        short_m = m.split("/")[-1] if "/" in m else m
                        new_p = {
                            "id": new_id,
                            "name": f"{short_m} ({base_name})",
                            "protocol": protocol,
                            "base_url": base_url,
                            "api_key": api_key,
                            "model": m,
                            "reasoning_override": "auto"
                        }
                        self.profiles.append(new_p)
                        self.combo_profiles.addItem(new_p["name"], new_id)
                        imported_count += 1

                    QMessageBox.information(
                        self,
                        "批量导入完成",
                        f"已成功批量导入 {imported_count} 个新配置！\n您可以在上方配置下拉框中随时切换使用。"
                    )

    def _on_prompt_mode_changed(self):
        mode = self.combo_prompt_mode.currentData()
        current_text = self.custom_prompts.get(mode, "")
        self.edit_prompt.setText(current_text)

    def _reset_current_prompt(self):
        mode = self.combo_prompt_mode.currentData()
        default_val = DEFAULT_PROMPTS.get(mode, "")
        self.edit_prompt.setText(default_val)
        self.custom_prompts[mode] = default_val

    def _save_all(self):
        self._save_current_form_to_profile()
        current_mode = self.combo_prompt_mode.currentData()
        self.custom_prompts[current_mode] = self.edit_prompt.toPlainText().strip()

        # 写回全局 settings
        settings.set("profiles", self.profiles)
        active_id = self.combo_profiles.currentData()
        settings.set("active_profile_id", active_id)
        settings.set("temperature", self.spin_temp.value())
        settings.set("custom_prompts", self.custom_prompts)

        # 思考模式与场景调度保存
        mode_map = {0: "auto", 1: "always_on", 2: "always_off", 3: "passthrough"}
        settings.set("reasoning_mode", mode_map.get(self.combo_reasoning_mode.currentIndex(), "auto"))

        effort_map = {0: "low", 1: "medium", 2: "high", 3: "dynamic"}
        settings.set("reasoning_effort", effort_map.get(self.combo_reasoning_effort.currentIndex(), "medium"))

        settings.set("fast_translate_threshold_chars", self.spin_fast_chars.value())
        settings.set("fast_translate_threshold_sentences", self.spin_fast_sentences.value())

        val_map = {0: "inherit", 1: "off", 2: "on", 3: "passthrough"}
        settings.set("feature_reasoning_overrides", {
            "dictionary": val_map.get(self.combo_override_dict.currentIndex(), "off"),
            "ocr": val_map.get(self.combo_override_ocr.currentIndex(), "off"),
            "fast_translate": val_map.get(self.combo_override_fast.currentIndex(), "off"),
            "deep_translate": val_map.get(self.combo_override_deep.currentIndex(), "inherit"),
            "polish": val_map.get(self.combo_override_polish.currentIndex(), "on")
        })

        # 常规与记忆设置保存
        new_theme = self.combo_theme.currentData()
        settings.set("app_theme", new_theme)
        ThemeManager.get_instance().apply_theme(new_theme)

        settings.set("output_format", self.combo_format.currentData())
        settings.set("history_limit", int(self.combo_history_limit.currentData()))
        settings.set("minimize_to_tray_on_close", self.check_minimize_tray.isChecked())
        settings.set("eco_mode", self.check_eco_mode.isChecked())

        self.settings_updated.emit()
        self.accept()

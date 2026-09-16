import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton, 
    QComboBox, QDoubleSpinBox, QFormLayout, QMessageBox,
    QCheckBox, QFrame
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Signal, QThread, Qt
from config.settings import (
    settings, DEFAULT_PROFILES, 
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_DESCRIPTION
)
from config.default_prompts import DEFAULT_PROMPTS
from core.history_manager import history_manager
from core.theme_manager import ThemeManager
from ui.components.model_probe_dialog import ModelProbeDialog

class TestConnectionWorker(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, base_url: str, api_key: str, model: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def run(self):
        client = LLMClient(self.base_url, self.api_key, self.model, timeout=30.0)
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

class SettingsDialog(QDialog):
    """Settings modal dialog."""
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置与模型配置 - Just Translate")
        self.setMinimumSize(600, 520)
        self.test_worker = None
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget()

        # Tab 1: 模型服务配置
        tab_models = QWidget()
        layout_models = QVBoxLayout(tab_models)
        layout_models.setSpacing(10)

        # Profile 切换与新建/删除栏
        profile_bar = QHBoxLayout()
        profile_bar.addWidget(QLabel("选择/切换配置:"))
        self.combo_profiles = QComboBox()
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

        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText("如 http://127.0.0.1:8080/v1 或 https://api.deepseek.com/v1")
        form_layout.addRow("Base URL:", self.edit_base_url)

        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.edit_api_key.setPlaceholderText("本地模型可留空或填 sk-no-key")
        form_layout.addRow("API Key:", self.edit_api_key)

        model_layout = QHBoxLayout()
        self.edit_model = QLineEdit()
        self.edit_model.setPlaceholderText("如 default, qwen2.5:7b, gpt-4o-mini 等")
        model_layout.addWidget(self.edit_model, 1)

        self.btn_probe = QPushButton("📡 探测模型")
        self.btn_probe.setObjectName("secondaryBtn")
        self.btn_probe.setToolTip("向当前 Base URL 发送请求，探测并自选/批量导入可用模型")
        self.btn_probe.clicked.connect(self._probe_models)
        model_layout.addWidget(self.btn_probe)

        form_layout.addRow("模型名称:", model_layout)

        self.edit_ocr_model = QLineEdit()
        self.edit_ocr_model.setPlaceholderText("选填，如 GLM-OCR、gpt-4o-mini、qwen-vl；留空则视为主模型")
        form_layout.addRow("OCR 识图模型 (选填):", self.edit_ocr_model)

        self.spin_temp = QDoubleSpinBox()
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
        self.tabs.addTab(tab_models, "模型服务")

        # Tab 2: 自定义系统提示词
        tab_prompts = QWidget()
        layout_prompts = QVBoxLayout(tab_prompts)
        layout_prompts.setSpacing(8)

        prompt_mode_bar = QHBoxLayout()
        prompt_mode_bar.addWidget(QLabel("选择模式:"))
        self.combo_prompt_mode = QComboBox()
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

        # Tab 3: 常规与记忆管理
        tab_general = QWidget()
        layout_general = QVBoxLayout(tab_general)
        layout_general.setSpacing(12)

        form_general = QFormLayout()
        form_general.setSpacing(10)

        # 界面显示主题
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("🌙 黑色主题", "dark")
        self.combo_theme.addItem("☀️ 白色主题", "light")
        self.combo_theme.addItem("💻 跟随系统", "system")
        form_general.addRow("界面显示主题:", self.combo_theme)

        # 默认输出格式
        self.combo_format = QComboBox()
        self.combo_format.addItem("📝 Markdown 格式 (支持标题、列表与富文本)", "markdown")
        self.combo_format.addItem("📄 纯文本格式 (Plain Text 无排版标记)", "plain")
        form_general.addRow("默认文本输出格式:", self.combo_format)

        # 记忆容量
        self.combo_history_limit = QComboBox()
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
        self.tabs.addTab(tab_general, "常规与记忆")

        # Tab 4: 关于
        tab_about = QWidget()
        layout_about = QVBoxLayout(tab_about)
        layout_about.setContentsMargins(24, 20, 24, 20)
        layout_about.setSpacing(16)

        # 头部 LOGO 与应用信息
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        header_layout.setSpacing(8)

        # 软件图标
        lbl_about_icon = QLabel()
        lbl_about_icon.setAlignment(Qt.AlignCenter)
        icon_path = self._resolve_icon_path()
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                lbl_about_icon.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_layout.addWidget(lbl_about_icon)

        # 软件名称
        lbl_about_title = QLabel(APP_NAME)
        lbl_about_title.setObjectName("aboutTitle")
        lbl_about_title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_about_title)

        # 软件标语/描述
        lbl_about_desc = QLabel(APP_DESCRIPTION)
        lbl_about_desc.setObjectName("aboutDesc")
        lbl_about_desc.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_about_desc)

        layout_about.addLayout(header_layout)

        # 信息卡片容器 (QFrame)
        info_card = QFrame()
        info_card.setObjectName("aboutCard")
        card_layout = QFormLayout(info_card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        card_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def make_value_label(text: str, is_highlight: bool = False) -> QLabel:
            lbl = QLabel(text)
            if is_highlight:
                lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #6366F1;")
            else:
                lbl.setStyleSheet("font-size: 13px;")
            return lbl

        card_layout.addRow("软件作者:", make_value_label(APP_AUTHOR, is_highlight=True))
        card_layout.addRow("版本号:", make_value_label(APP_VERSION))
        card_layout.addRow("技术架构:", make_value_label("Python 3.10+ / PySide6 (Qt 6) / Edge Neural TTS / GLM-OCR"))
        card_layout.addRow("核心模式:", make_value_label("精准翻译 (Translate) / 母语润色 (Polish) / 结构化卡片词典 (Dictionary)"))
        card_layout.addRow("开源协议:", make_value_label("MIT License"))

        layout_about.addWidget(info_card)

        # 底部版权声明
        layout_about.addStretch()
        lbl_copyright = QLabel(f"© 2026 {APP_AUTHOR}. All rights reserved.")
        lbl_copyright.setObjectName("aboutCopyright")
        lbl_copyright.setAlignment(Qt.AlignCenter)
        layout_about.addWidget(lbl_copyright)

        self.tabs.addTab(tab_about, "关于")

        main_layout.addWidget(self.tabs)

        # 对话框底部按钮
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("保存配置")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._save_all)
        btn_box.addWidget(self.btn_save)

        main_layout.addLayout(btn_box)

    def _resolve_icon_path(self) -> Path:
        """Resolves application icon path in dev and frozen environments."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        p = base_dir / "resources" / "icon.png"
        if p.exists():
            return p
        if getattr(sys, "frozen", False):
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

    def _save_current_form_to_profile(self):
        idx = self.combo_profiles.currentIndex()
        if 0 <= idx < len(self.profiles):
            self.profiles[idx]["name"] = self.edit_name.text().strip()
            self.profiles[idx]["base_url"] = self.edit_base_url.text().strip()
            self.profiles[idx]["api_key"] = self.edit_api_key.text().strip()
            self.profiles[idx]["model"] = self.edit_model.text().strip()
            self.profiles[idx]["ocr_model"] = self.edit_ocr_model.text().strip()
            # 同步更新 combo 显示名称
            self.combo_profiles.setItemText(idx, self.profiles[idx]["name"])

    def _on_profile_selected(self, index: int):
        self._load_current_profile_form()
        self.lbl_test_result.setText("")

    def _add_profile(self):
        new_id = f"custom_{len(self.profiles) + 1}"
        new_p = {
            "id": new_id,
            "name": f"自定义配置 {len(self.profiles) + 1}",
            "base_url": "http://127.0.0.1:8080/v1",
            "api_key": "",
            "model": "default"
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

        if not base_url:
            self.lbl_test_result.setText("<span style='color:#EF4444;'>Base URL 不能为空</span>")
            return

        self.btn_test.setEnabled(False)
        self.lbl_test_result.setText("⏳ 正在测试连接 (最大等待 30 秒)...")

        self.test_worker = TestConnectionWorker(base_url, api_key, model)
        self.test_worker.result_signal.connect(self._on_test_finished)
        self.test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_result.setText(f"<span style='color:#10B981;'>✓ {message}</span>")
        else:
            self.lbl_test_result.setText(f"<span style='color:#EF4444;'>✗ {message}</span>")

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
                    imported_count = 0

                    for m in dialog.chosen_models_batch:
                        # 检查是否已存在同端点同模型
                        exists = any(p.get("base_url") == base_url and p.get("model") == m for p in self.profiles)
                        if exists:
                            continue
                        new_id = f"imported_{len(self.profiles) + 1}"
                        short_m = m.split("/")[-1] if "/" in m else m
                        new_p = {
                            "id": new_id,
                            "name": f"{short_m} ({base_name})",
                            "base_url": base_url,
                            "api_key": api_key,
                            "model": m
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
        # 先保存之前模式的文本
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

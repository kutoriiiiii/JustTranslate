# -*- coding: utf-8 -*-
"""History viewer and management dialog for Just Translate."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
    QWidget, QLabel, QLineEdit, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QTextBrowser, QMessageBox,
    QApplication, QFrame
)
from PySide6.QtCore import Signal, Qt
from config.settings import settings
from core.history_manager import history_manager
from .balanced_splitter import BalancedSplitter
from ui.components.wheel_filter import NoWheelComboBox

class HistoryDialog(QDialog):
    """Dialog for viewing, searching, copying, and re-importing past translation & generation history."""

    import_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记忆与历史记录 - Just Translate")
        self.resize(880, 580)
        self._current_records = []
        self._selected_record = None

        self._init_ui()
        self._load_records()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. 顶部控制与过滤栏
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 搜索原文、输出结果或模型名称...")
        self.edit_search.textChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self.edit_search, 1)

        top_bar.addWidget(QLabel("模式:"))
        self.combo_mode = NoWheelComboBox()
        self.combo_mode.addItem("全部模式", "all")
        self.combo_mode.addItem("翻译", "translate")
        self.combo_mode.addItem("润色", "polish")
        self.combo_mode.addItem("词典", "dictionary")
        self.combo_mode.currentIndexChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self.combo_mode)

        self.lbl_count = QLabel("已保存: 0 / 100 条")
        self.lbl_count.setObjectName("statusLabel")
        top_bar.addWidget(self.lbl_count)

        self.btn_clear_all = QPushButton("🗑 清空历史")
        self.btn_clear_all.setObjectName("dangerBtn")
        self.btn_clear_all.clicked.connect(self._on_clear_all)
        top_bar.addWidget(self.btn_clear_all)

        main_layout.addLayout(top_bar)

        # 2. 中间左右分栏 (使用防塌陷且支持双击对等重置的 BalancedSplitter)
        splitter = BalancedSplitter(Qt.Horizontal, self)

        # 左侧列表
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(180)
        self.list_widget.currentRowChanged.connect(self._on_record_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        splitter.addWidget(self.list_widget)

        # 右侧详情展示区
        right_panel = QWidget()
        right_panel.setMinimumWidth(280)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # 元数据展示卡片
        self.card_meta = QFrame()
        self.card_meta.setObjectName("panelBox")
        meta_layout = QVBoxLayout(self.card_meta)
        meta_layout.setContentsMargins(10, 8, 10, 8)
        meta_layout.setSpacing(4)

        self.lbl_meta_time = QLabel("时间: -")
        self.lbl_meta_time.setObjectName("metaTime")
        self.lbl_meta_model = QLabel("模型: -")
        self.lbl_meta_model.setObjectName("metaModel")
        self.lbl_meta_perf = QLabel("性能: -")
        self.lbl_meta_perf.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 500;")

        meta_layout.addWidget(self.lbl_meta_time)
        meta_layout.addWidget(self.lbl_meta_model)
        meta_layout.addWidget(self.lbl_meta_perf)
        right_layout.addWidget(self.card_meta)

        # 原文展示
        lbl_in = QLabel("原文内容:")
        lbl_in.setObjectName("headerTitle")
        right_layout.addWidget(lbl_in)

        self.browser_input = QTextBrowser()
        self.browser_input.setPlaceholderText("选择左侧记录以查看原文...")
        self.browser_input.setMaximumHeight(160)
        right_layout.addWidget(self.browser_input)

        # 译文/结果展示
        lbl_out = QLabel("输出结果:")
        lbl_out.setObjectName("headerTitle")
        right_layout.addWidget(lbl_out)

        self.browser_output = QTextBrowser()
        self.browser_output.setPlaceholderText("选择左侧记录以查看生成结果...")
        right_layout.addWidget(self.browser_output, 1)

        # 底部操作按钮
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.btn_import = QPushButton("↩️ 导入回主工作区")
        self.btn_import.setObjectName("primaryBtn")
        self.btn_import.setToolTip("将本条原文导入到对应的工作区输入框，并切换到对应模式")
        self.btn_import.clicked.connect(self._on_import_clicked)
        action_bar.addWidget(self.btn_import)

        self.btn_copy_input = QPushButton("📋 复制原文")
        self.btn_copy_input.setObjectName("secondaryBtn")
        self.btn_copy_input.clicked.connect(self._copy_input)
        action_bar.addWidget(self.btn_copy_input)

        self.btn_copy_output = QPushButton("📋 复制结果")
        self.btn_copy_output.setObjectName("secondaryBtn")
        self.btn_copy_output.clicked.connect(self._copy_output)
        action_bar.addWidget(self.btn_copy_output)

        self.btn_delete = QPushButton("🗑 删除此条")
        self.btn_delete.setObjectName("secondaryBtn")
        self.btn_delete.clicked.connect(self._on_delete_selected)
        action_bar.addWidget(self.btn_delete)

        right_layout.addLayout(action_bar)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter, 1)

    def _load_records(self):
        mode = self.combo_mode.currentData()
        keyword = self.edit_search.text().strip()
        limit = int(settings.get("history_limit", 100))

        records = history_manager.get_records(mode=mode, keyword=keyword, limit=limit)
        total_count = history_manager.get_count()
        self.lbl_count.setText(f"已保存: {total_count} / {limit} 条")

        self._current_records = records
        self.list_widget.clear()

        mode_name_map = {
            "translate": "翻译",
            "polish": "润色",
            "dictionary": "词典"
        }

        for r in records:
            time_str = r.get("created_at", "")[5:]  # 去掉年份简写 MM-DD HH:MM:SS
            m_str = mode_name_map.get(r.get("mode"), r.get("mode"))
            src = r.get("source_lang", "")
            tgt = r.get("target_lang", "")
            lang_pair = f"{src} ➔ {tgt}" if tgt else src
            
            in_preview = r.get("input_text", "").replace("\n", " ").strip()
            if len(in_preview) > 36:
                in_preview = in_preview[:36] + "..."

            perf_summary = f"{r.get('model', '')} | TTFT: {r.get('ttft_ms', 0)}ms"
            
            title_line = f"[{m_str}] {time_str} ({lang_pair})"
            display_text = f"{title_line}\n{in_preview}\n{perf_summary}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, r["id"])
            self.list_widget.addItem(item)

        if records:
            self.list_widget.setCurrentRow(0)
        else:
            self._clear_detail_view()

    def _on_filter_changed(self):
        self._load_records()

    def _on_record_selected(self, row: int):
        if 0 <= row < len(self._current_records):
            r = self._current_records[row]
            self._selected_record = r

            mode_name_map = {"translate": "翻译", "polish": "润色", "dictionary": "词典"}
            m_str = mode_name_map.get(r.get("mode"), r.get("mode"))

            self.lbl_meta_time.setText(f"[{m_str}] 时间: {r.get('created_at')}  |  语言: {r.get('source_lang')} ➔ {r.get('target_lang')}")
            self.lbl_meta_model.setText(f"模型: {r.get('model')}")
            self.lbl_meta_perf.setText(
                f"⚡ 首字延迟: {r.get('ttft_ms', 0)} ms   "
                f"🚀 速率: {r.get('speed_tok_s', 0)} tok/s   "
                f"⏱ 总耗时: {r.get('duration_s', 0)} s"
            )

            self.browser_input.setPlainText(r.get("input_text", ""))
            
            # 使用 Markdown 渲染输出
            output_text = r.get("output_text", "")
            if settings.get("output_format", "markdown") == "plain":
                self.browser_output.setPlainText(output_text)
            else:
                from core.text_utils import render_markdown_to_html
                self.browser_output.setHtml(render_markdown_to_html(output_text))
        else:
            self._clear_detail_view()

    def _clear_detail_view(self):
        self._selected_record = None
        self.lbl_meta_time.setText("时间: -")
        self.lbl_meta_model.setText("模型: -")
        self.lbl_meta_perf.setText("性能: -")
        self.browser_input.clear()
        self.browser_output.clear()

    def _on_item_double_clicked(self, item):
        self._on_import_clicked()

    def _on_import_clicked(self):
        if self._selected_record:
            self.import_requested.emit(self._selected_record)
            self.accept()

    def _copy_input(self):
        if self._selected_record:
            text = self._selected_record.get("input_text", "").strip()
            if text:
                QApplication.clipboard().setText(text)
                self.btn_copy_input.setText("✓ 已复制")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self.btn_copy_input.setText("📋 复制原文"))

    def _copy_output(self):
        if self._selected_record:
            text = self._selected_record.get("output_text", "").strip()
            if text:
                QApplication.clipboard().setText(text)
                self.btn_copy_output.setText("✓ 已复制")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self.btn_copy_output.setText("📋 复制结果"))

    def _on_delete_selected(self):
        if not self._selected_record:
            return
        
        rid = self._selected_record.get("id")
        if history_manager.delete_record(rid):
            self._load_records()

    def _on_clear_all(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有已保存的历史记忆记录吗？此操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            history_manager.clear_all()
            self._load_records()

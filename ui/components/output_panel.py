# -*- coding: utf-8 -*-
"""Right output panel with markdown/plain-text rendering, streaming display, copy, stop, retry, and sentence-level comparison/actions."""

from typing import Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextBrowser, QSpacerItem, QSizePolicy, QApplication,
    QComboBox, QTextEdit
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor, QColor
from config.settings import settings
from core.sentence_aligner import split_sentences_with_spans, find_sentence_at_position, SentenceSpan
from core.tts_manager import tts_manager
from core.theme_manager import ThemeManager
from ui.components.wheel_filter import NoWheelComboBox

class CustomOutputBrowser(QTextBrowser):
    """Browser supporting sentence double-click selection, non-destructive highlighting, and contextual sentence actions."""

    sentence_selected = Signal(int, str, int) # (sentence_index, sentence_text, total_sentences)
    translate_sentence_requested = Signal(int, str) # (sentence_index, sentence_text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self._current_sentence_span: Optional[SentenceSpan] = None

    def mouseDoubleClickEvent(self, event):
        """Intercepts double click to select entire translated sentence and trigger cross-box alignment."""
        cursor = self.cursorForPosition(event.pos())
        pos = cursor.position()
        text = self.toPlainText()
        spans = split_sentences_with_spans(text)
        span = find_sentence_at_position(spans, pos)
        if span:
            cur = self.textCursor()
            cur.setPosition(span.start)
            cur.setPosition(span.end, QTextCursor.KeepAnchor)
            self.setTextCursor(cur)
            self._current_sentence_span = span
            self.sentence_selected.emit(span.index, span.text, len(spans))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clear_highlight()
        super().mousePressEvent(event)

    def highlight_sentence(self, index: int):
        """Highlights the sentence at index using ExtraSelection and smoothly scrolls to view."""
        text = self.toPlainText()
        spans = split_sentences_with_spans(text)
        if 0 <= index < len(spans):
            span = spans[index]
            cur = self.textCursor()
            cur.setPosition(span.start)
            cur.setPosition(span.end, QTextCursor.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cur
            selection.format.setBackground(QColor(16, 185, 129, 85)) # Subtle vibrant Emerald Green tint
            self.setExtraSelections([selection])

            # Scroll view without breaking user selection
            view_cur = self.textCursor()
            view_cur.setPosition(span.start)
            self.setTextCursor(view_cur)
            self.ensureCursorVisible()
            self._current_sentence_span = span

    def clear_highlight(self):
        """Clears ExtraSelection highlighting."""
        self.setExtraSelections([])
        self._current_sentence_span = None

    def contextMenuEvent(self, event):
        """Provides right-click context menu with localized icons and single-sentence actions."""
        menu = self.createStandardContextMenu()
        icon_map = {
            "copy link location": "🔗 复制链接地址",
            "copy": "📋 复制",
            "select all": "📑 全选",
        }
        for act in menu.actions():
            clean = act.text().replace("&", "")
            for key, val in icon_map.items():
                if key in clean.lower():
                    if "\t" in clean:
                        shortcut = clean.split("\t")[-1]
                        act.setText(f"{val}\t{shortcut}")
                    else:
                        act.setText(val)
                    break

        cursor = self.cursorForPosition(event.pos())
        pos = cursor.position()
        spans = split_sentences_with_spans(self.toPlainText())
        parent_panel = self.parent()
        lang = parent_panel.get_language() if hasattr(parent_panel, "get_language") else None

        if span:
            menu.addSeparator()
            action_retranslate = menu.addAction(f"🌐 重新翻译此句 (第 {span.index + 1} 句)")
            action_retranslate.triggered.connect(lambda: self.translate_sentence_requested.emit(span.index, span.text))
            action_copy_sentence = menu.addAction("📋 复制当前整句")
            action_copy_sentence.triggered.connect(lambda: QApplication.clipboard().setText(span.text))
            action_tts_sentence = menu.addAction("🔊 朗读当前整句")
            action_tts_sentence.triggered.connect(lambda: tts_manager.speak(span.text, lang=lang, parent_widget=self))

        # TTS 全文/选区与模型下载设置
        menu.addSeparator()
        selected_text = self.textCursor().selectedText().strip()
        if selected_text:
            action_tts_sel = menu.addAction("🔊 朗读所选文字")
            action_tts_sel.triggered.connect(lambda: tts_manager.speak(selected_text, lang=lang, parent_widget=self))
        else:
            full_text = self.toPlainText().strip()
            if full_text:
                action_tts_all = menu.addAction("🔊 朗读全文 (TTS)")
                action_tts_all.triggered.connect(lambda: tts_manager.speak(full_text, lang=lang, parent_widget=self))

        if tts_manager.is_speaking():
            action_stop_tts = menu.addAction("⏹ 停止语音朗读")
            action_stop_tts.triggered.connect(tts_manager.stop)

        menu.exec(event.globalPos())

class OutputPanel(QFrame):
    """Panel displaying streaming output with selectable Markdown/Plain-text formatting and contextual action buttons."""

    stop_requested = Signal()
    retry_requested = Signal()
    format_changed = Signal(str)
    one_click_polish_requested = Signal(str)
    one_click_back_translate_requested = Signal(str)
    sentence_selected = Signal(int, str, int)
    translate_sentence_requested = Signal(int, str)

    def __init__(
        self, 
        parent=None, 
        title: str = "结果展示", 
        copy_btn_text: str = "📋 复制结果", 
        copy_extractor=None, 
        copy_tooltip: str = "",
        show_extra_actions: bool = False,
        mode: str = "translate"
    ):
        super().__init__(parent)
        self.setObjectName("panelBox")
        self.setMinimumWidth(280)
        self.panel_title = title
        self.copy_btn_text = copy_btn_text
        self.copy_extractor = copy_extractor
        self.copy_tooltip = copy_tooltip
        self.show_extra_actions = show_extra_actions
        self.mode = mode
        self._raw_text = ""
        self._is_generating = False

        self.btn_polish = None
        self.btn_back_translate = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 1. 顶部标题、状态与格式切换器
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel(self.panel_title)
        self.lbl_title.setObjectName("headerTitle")
        header_layout.addWidget(self.lbl_title)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("statusLabel")
        header_layout.addWidget(self.lbl_status)

        # 琥珀色原文修改过期预警标签 (轻量、常驻但不碍眼，默认隐藏)
        self.lbl_stale_warning = QLabel("⚠ 原文已修改，结果可能不准确")
        self.lbl_stale_warning.setObjectName("staleWarningLabel")
        self.lbl_stale_warning.setStyleSheet("""
            color: #F59E0B;
            background-color: rgba(245, 158, 11, 0.12);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 11px;
            font-weight: 500;
        """)
        self.lbl_stale_warning.setVisible(False)
        header_layout.addWidget(self.lbl_stale_warning)

        header_layout.addStretch()

        # 输出格式开关 (Markdown / 纯文本)
        lbl_fmt = QLabel("格式:")
        lbl_fmt.setObjectName("statusLabel")
        header_layout.addWidget(lbl_fmt)

        self.combo_format = NoWheelComboBox()
        self.combo_format.setCursor(Qt.PointingHandCursor)
        self.combo_format.addItem("✨ Markdown 渲染", "markdown")
        self.combo_format.addItem("📄 纯文本", "plain")
        
        current_fmt = settings.get("output_format", "markdown")
        self.combo_format.setCurrentIndex(1 if current_fmt == "plain" else 0)
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        header_layout.addWidget(self.combo_format)

        layout.addLayout(header_layout)

        # 2. 富文本/Markdown/纯文本内容展示框 (使用定制的 CustomOutputBrowser)
        self.browser = CustomOutputBrowser()
        self.browser.setPlaceholderText("处理结果将在此流式展现 (双击句子即可逐句对照与复制)...")
        self.browser.sentence_selected.connect(self._on_sentence_selected)
        self.browser.translate_sentence_requested.connect(self.translate_sentence_requested.emit)
        layout.addWidget(self.browser)

        # 3. 底部双排对称操作栏
        footer_layout = QVBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(6)

        # 第 1 排：智能辅助与单句重译排（左侧单句重译，右侧润色/回译/TTS朗读）
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("statusLabel")
        row1.addWidget(self.lbl_info)

        # 单独重新翻译/微调选定句按钮
        self.btn_retranslate_sentence = QPushButton("🌐 单独重译此句")
        self.btn_retranslate_sentence.setObjectName("accentBtnEmerald")
        self.btn_retranslate_sentence.setCursor(Qt.PointingHandCursor)
        self.btn_retranslate_sentence.setToolTip("双击译文句子或将光标置于某句，点击此按钮可呼出单句独立翻译与对照微调卡片")
        self.btn_retranslate_sentence.clicked.connect(self._on_retranslate_sentence_btn_clicked)
        row1.addWidget(self.btn_retranslate_sentence)

        row1.addStretch()

        # 仅在翻译模式下启用：一键润色与一键回译
        if self.show_extra_actions:
            self.btn_polish = QPushButton("✨ 一键润色")
            self.btn_polish.setObjectName("secondaryBtn")
            self.btn_polish.setCursor(Qt.PointingHandCursor)
            self.btn_polish.setToolTip("将当前翻译结果直接导入润色模式并立即优化生成")
            self.btn_polish.setEnabled(False)
            self.btn_polish.clicked.connect(self._on_one_click_polish)
            row1.addWidget(self.btn_polish)

            self.btn_back_translate = QPushButton("🔁 一键回译")
            self.btn_back_translate.setObjectName("secondaryBtn")
            self.btn_back_translate.setCursor(Qt.PointingHandCursor)
            self.btn_back_translate.setToolTip("将当前翻译结果反向翻译回原文语言并立即生成")
            self.btn_back_translate.setEnabled(False)
            self.btn_back_translate.clicked.connect(self._on_one_click_back_translate)
            row1.addWidget(self.btn_back_translate)

        # TTS 语音朗读按钮
        self.btn_tts = QPushButton("🔊 朗读")
        self.btn_tts.setObjectName("secondaryBtn")
        self.btn_tts.setCursor(Qt.PointingHandCursor)
        self.btn_tts.setToolTip("点击朗读生成结果 (再次点击停止)")
        self.btn_tts.clicked.connect(self._toggle_tts)
        row1.addWidget(self.btn_tts)

        footer_layout.addLayout(row1)

        # 第 2 排：基础操作与主行动排（左侧停止/重试，右侧复制结果）
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # 停止生成
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setToolTip("停止当前流式生成")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        row2.addWidget(self.btn_stop)

        # 重新生成
        self.btn_retry = QPushButton("🔄 重试")
        self.btn_retry.setObjectName("secondaryBtn")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setToolTip("使用当前输入重新生成")
        self.btn_retry.clicked.connect(self.retry_requested.emit)
        row2.addWidget(self.btn_retry)

        row2.addStretch()

        # 复制按钮
        self.btn_copy = QPushButton(self.copy_btn_text)
        self.btn_copy.setObjectName("secondaryBtn")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        if self.copy_tooltip:
            self.btn_copy.setToolTip(self.copy_tooltip)
        self.btn_copy.clicked.connect(self._copy_result)
        row2.addWidget(self.btn_copy)

        footer_layout.addLayout(row2)

        layout.addLayout(footer_layout)

        # 连接全局 TTS 停止信号同步按钮状态
        tts_manager.speech_finished.connect(self._on_tts_finished)

        # 连接全局主题变更信号，即刻重绘 Markdown 输出
        ThemeManager.get_instance().theme_changed.connect(self._on_theme_changed)

    def get_language(self) -> str:
        """Returns the current target language (or source language if in polish mode)."""
        win = self.window()
        if win and hasattr(win, "control_bar"):
            mode = win.control_bar.get_current_mode()
            src_lang, target_lang = win.control_bar.get_languages()
            if mode == "polish":
                return src_lang
            return target_lang
        return "Auto"

    def _toggle_tts(self):
        if tts_manager.is_speaking():
            tts_manager.stop()
            self.btn_tts.setText("🔊 朗读")
        else:
            text = self.get_raw_text().strip()
            if text:
                tts_manager.speak(text, lang=self.get_language(), parent_widget=self)
                self.btn_tts.setText("⏹ 停止朗读")

    def _on_tts_finished(self):
        self.btn_tts.setText("🔊 朗读")

    def start_streaming(self, *args, **kwargs):
        """Prepares the view for receiving new stream chunks."""
        self._raw_text = ""
        self._is_generating = True
        self.browser.clear()
        self.browser.clear_highlight()
        self.btn_stop.setEnabled(True)
        self.btn_retry.setEnabled(False)
        if self.btn_polish:
            self.btn_polish.setEnabled(False)
        if self.btn_back_translate:
            self.btn_back_translate.setEnabled(False)
        self.lbl_status.setText("正在连接...")

    def append_chunk(self, chunk: str):
        """Appends a new streamed chunk to the display view."""
        self._raw_text += chunk
        self.browser.moveCursor(QTextCursor.End)
        self.browser.insertPlainText(chunk)
        self.browser.moveCursor(QTextCursor.End)

    def finish_streaming(self, final_text: str = None):
        """Finalizes streaming and applies chosen formatting styling with anti-flicker focus protection."""
        self._is_generating = False
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)
        if final_text is not None:
            self._raw_text = final_text

        # 自动过滤模型可能输出的前缀指令复述
        if self._raw_text:
            from core.text_utils import strip_unwanted_prefixes
            self._raw_text = strip_unwanted_prefixes(self._raw_text)

        has_text = bool(self._raw_text.strip())
        if self.btn_polish:
            self.btn_polish.setEnabled(has_text)
        if self.btn_back_translate:
            self.btn_back_translate.setEnabled(has_text)

        self._apply_current_format(is_stream_finish=True)

    def stop_streaming(self, partial_text: str = None):
        """Finalizes streaming when cancelled or stopped by user without clearing partial content."""
        self._is_generating = False
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)
        if partial_text is not None:
            self._raw_text = partial_text
        has_text = bool(self._raw_text.strip())
        if self.btn_polish:
            self.btn_polish.setEnabled(has_text)
        if self.btn_back_translate:
            self.btn_back_translate.setEnabled(has_text)
        self.lbl_status.setText("已停止")

    def set_stale_warning(self, visible: bool):
        """Displays or hides the amber stale warning badge."""
        self.lbl_stale_warning.setVisible(visible)

    def set_title(self, title: str):
        """Dynamically updates the panel header title."""
        self.lbl_title.setText(title)

    @staticmethod
    def _prepare_markdown(raw_text: str) -> str:
        """Ensures single newlines are treated as hard breaks in CommonMark rendering, preventing words from collapsing."""
        lines = raw_text.splitlines()
        processed = []
        in_code_block = False
        for line in lines:
            stripped = line.rstrip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                processed.append(stripped)
            elif in_code_block:
                processed.append(line)
            elif stripped.startswith(("#", "-", "*", ">", "|")) or not stripped:
                processed.append(stripped)
            else:
                processed.append(stripped + "  ")
        return "\n".join(processed)

    def _safe_update_browser(self, content: str, is_html: bool):
        """Updates browser content while freezing repainting and preserving viewport scroll anchor."""
        scroll_bar = self.browser.verticalScrollBar()
        old_val = scroll_bar.value()
        old_max = scroll_bar.maximum()
        # 用户在底部附近（正常随流式阅读到文末）或无滚动条
        is_at_bottom = (old_max == 0) or (old_max - old_val <= 30)
        ratio = (old_val / old_max) if old_max > 0 else 0.0

        # 冻结重绘，消除白色闪烁与视觉焦点跳跃
        self.browser.setUpdatesEnabled(False)
        try:
            if is_html:
                self.browser.setHtml(content)
            else:
                self.browser.setPlainText(content)

            new_max = scroll_bar.maximum()
            if is_at_bottom:
                self.browser.moveCursor(QTextCursor.End)
                scroll_bar.setValue(new_max)
            else:
                scroll_bar.setValue(int(ratio * new_max))
        finally:
            self.browser.setUpdatesEnabled(True)

    def _apply_current_format(self, is_stream_finish: bool = False):
        """Applies Markdown or Plain Text formatting based on current combo selection.

        If is_stream_finish is True and the content contains no complex Markdown features,
        skips setHtml re-rendering completely to protect visual focus.
        """
        text = self._raw_text.strip()
        if not text:
            return

        fmt = self.combo_format.currentData()
        if fmt == "plain":
            if self.browser.toPlainText().strip() != text:
                self._safe_update_browser(text, is_html=False)
            return

        from core.text_utils import has_markdown_features, render_markdown_to_html

        # 流式刚结束时的无感防闪烁与阅读焦点保护：
        # 1. 润色模式：直接保留流式打字的纯文本排版状态，彻底消除流式结束瞬间的页面刷新与焦点丢失；
        # 2. 翻译模式：若内容为常规段落/文本（无表格、代码块等复杂结构），同样保持流式纯文本，不进行 HTML 重渲染。
        should_skip_html = False
        if is_stream_finish:
            if self.mode == "polish":
                should_skip_html = True
            elif not has_markdown_features(text):
                should_skip_html = True

        if should_skip_html:
            current_text = self.browser.toPlainText().strip()
            # 仅在清理前缀导致文字有变动时才轻量刷新纯文本，否则保持原样（0 闪烁、0 焦点丢失）
            if current_text != text:
                self._safe_update_browser(text, is_html=False)
            return

        # 用户主动切换格式/主题，或翻译模式中包含富文本语法时，执行带视口锁定的 HTML 渲染
        styled_html = render_markdown_to_html(self._raw_text)
        self._safe_update_browser(styled_html, is_html=True)

    def _on_theme_changed(self, mode: str, is_dark: bool):
        """Immediately re-renders existing output when the theme changes."""
        self._apply_current_format()

    def _on_format_changed(self):
        fmt = self.combo_format.currentData()
        settings.set("output_format", fmt)
        self._apply_current_format()
        self.format_changed.emit(fmt)

    def set_format(self, fmt: str):
        """Synchronizes format with external state."""
        self.combo_format.blockSignals(True)
        self.combo_format.setCurrentIndex(1 if fmt == "plain" else 0)
        self.combo_format.blockSignals(False)
        self._apply_current_format()

    def highlight_sentence(self, index: int):
        """Highlights sentence at index."""
        self.browser.highlight_sentence(index)

    def clear_highlight(self):
        """Clears highlight in the output browser."""
        self.browser.clear_highlight()

    def _on_sentence_selected(self, index: int, text: str, total: int):
        self.btn_retranslate_sentence.setText(f"🌐 单独重译此句 (第 {index + 1}/{total} 句)")
        self.sentence_selected.emit(index, text, total)

    def _on_retranslate_sentence_btn_clicked(self):
        text = self.get_raw_text().strip()
        if text:
            spans = split_sentences_with_spans(text)
            if self.browser._current_sentence_span:
                span = self.browser._current_sentence_span
            else:
                pos = self.browser.textCursor().position()
                span = find_sentence_at_position(spans, pos)
            if span:
                self.browser.highlight_sentence(span.index)
                self.btn_retranslate_sentence.setText(f"🌐 单独重译此句 (第 {span.index + 1}/{len(spans)} 句)")
                self.translate_sentence_requested.emit(span.index, span.text)

    def replace_sentence_at_index(self, sentence_index: int, new_sentence_text: str):
        """Replaces a specific sentence in the output text and updates display with highlighting."""
        spans = split_sentences_with_spans(self._raw_text)
        if 0 <= sentence_index < len(spans):
            target_span = spans[sentence_index]
            new_raw = self._raw_text[:target_span.start] + new_sentence_text + self._raw_text[target_span.end:]
            self._raw_text = new_raw
            self._apply_current_format()
            self.highlight_sentence(sentence_index)

    def show_error(self, error_msg: str):
        """Displays error message with styled warning."""
        self._is_generating = False
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)
        if self.btn_polish:
            self.btn_polish.setEnabled(False)
        if self.btn_back_translate:
            self.btn_back_translate.setEnabled(False)
        self.lbl_status.setText("出错了")
        styled_err = f"<div style='color: #EF4444; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 6px; border: 1px solid #EF4444;'>" \
                     f"<b>❌ 请求异常：</b><br>{error_msg}</div>"
        self.browser.setHtml(styled_err)

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def _on_stop(self):
        self.stop_requested.emit()
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("正在中断...")

    def _on_one_click_polish(self):
        if self._raw_text.strip():
            self.one_click_polish_requested.emit(self._raw_text.strip())

    def _on_one_click_back_translate(self):
        if self._raw_text.strip():
            self.one_click_back_translate_requested.emit(self._raw_text.strip())

    def _copy_result(self):
        raw = self._raw_text
        if self.copy_extractor:
            text_to_copy = self.copy_extractor(raw)
        else:
            text_to_copy = raw

        text_to_copy = text_to_copy.strip()
        if text_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_to_copy)
            original_text = self.btn_copy.text()
            feedback = "✓ 已复制正文" if self.copy_extractor else "✓ 已复制"
            self.btn_copy.setText(feedback)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy.setText(original_text))

    def get_raw_text(self) -> str:
        return self._raw_text

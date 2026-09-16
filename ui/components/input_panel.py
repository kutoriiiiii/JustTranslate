# -*- coding: utf-8 -*-
"""Left input panel with text editing, image upload, clipboard image paste, drag & drop, and preview card."""

import io
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QPlainTextEdit, QSpacerItem, QSizePolicy, 
    QApplication, QFileDialog, QWidget, QTextEdit
)
from PySide6.QtCore import Signal, Qt, QBuffer
from PySide6.QtGui import QKeyEvent, QPixmap, QImage, QTextCursor, QColor
from core.sentence_aligner import split_sentences_with_spans, find_sentence_at_position, SentenceSpan
from core.tts_manager import tts_manager

class CustomInputEdit(QPlainTextEdit):
    """Text edit capable of sentence-level double-click selection, image pastes and Ctrl+Enter submission."""

    submit_triggered = Signal()
    image_pasted = Signal(object) # QImage or PIL Image
    file_dropped = Signal(str)
    sentence_selected = Signal(int, str, int) # (sentence_index, sentence_text, total_sentences)
    translate_sentence_requested = Signal(int, str) # (sentence_index, sentence_text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._current_sentence_span: Optional[SentenceSpan] = None

    def mouseDoubleClickEvent(self, event):
        """Intercepts double-click to select whole sentence for convenient comparison and copy."""
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
        """Applies non-destructive visual highlight to the sentence at index and scrolls into view."""
        text = self.toPlainText()
        spans = split_sentences_with_spans(text)
        if 0 <= index < len(spans):
            span = spans[index]
            cur = self.textCursor()
            cur.setPosition(span.start)
            cur.setPosition(span.end, QTextCursor.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cur
            selection.format.setBackground(QColor(2, 132, 199, 85)) # Vibrant Sky Blue tint
            self.setExtraSelections([selection])

            # Scroll view without altering user cursor selection permanently
            view_cur = self.textCursor()
            view_cur.setPosition(span.start)
            self.setTextCursor(view_cur)
            self.ensureCursorVisible()
            self._current_sentence_span = span

    def clear_highlight(self):
        """Clears cross-box extra selection highlights."""
        self.setExtraSelections([])
        self._current_sentence_span = None

    def contextMenuEvent(self, event):
        """Enriches standard context menu with localized icons and sentence actions."""
        menu = self.createStandardContextMenu()
        icon_map = {
            "undo": "↩ 撤销",
            "redo": "↪ 重做",
            "cut": "✂ 剪切",
            "copy": "📋 复制",
            "paste": "📥 粘贴",
            "delete": "🗑 删除",
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
        span = find_sentence_at_position(spans, pos)
        parent_panel = self.parent()
        lang = parent_panel.get_language() if hasattr(parent_panel, "get_language") else None

        if span:
            menu.addSeparator()
            action_translate = menu.addAction(f"🌐 单独翻译此句 (第 {span.index + 1} 句)")
            action_translate.triggered.connect(lambda: self.translate_sentence_requested.emit(span.index, span.text))
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

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                self.submit_triggered.emit()
                return
        elif event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime:
                if mime.hasImage():
                    img = clipboard.image()
                    if not img.isNull():
                        self.image_pasted.emit(img)
                        return
                if mime.hasUrls():
                    for url in mime.urls():
                        f_path = url.toLocalFile()
                        if f_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                            self.file_dropped.emit(f_path)
                            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source:
            if source.hasImage():
                img = source.imageData()
                if isinstance(img, QImage) and not img.isNull():
                    self.image_pasted.emit(img)
                    return
                cb_img = QApplication.clipboard().image()
                if not cb_img.isNull():
                    self.image_pasted.emit(cb_img)
                    return
            if source.hasUrls():
                for url in source.urls():
                    f_path = url.toLocalFile()
                    if f_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                        self.file_dropped.emit(f_path)
                        return
        super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                f_path = url.toLocalFile()
                if f_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    self.file_dropped.emit(f_path)
                    event.acceptProposedAction()
                    return
        elif event.mimeData().hasImage():
            img = event.mimeData().imageData()
            if img:
                self.image_pasted.emit(img)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

MODE_BUTTON_TEXTS = {
    "translate": "🚀 翻译",
    "polish": "✨ 润色",
    "dictionary": "🔎 查询",
}

class InputPanel(QFrame):
    """Panel containing user input text area, image loader/preview, and quick action controls."""

    submit_requested = Signal(str, object)
    user_text_changed = Signal(str)
    sentence_selected = Signal(int, str, int)
    translate_sentence_requested = Signal(int, str)

    def __init__(self, parent=None, title: str = "输入文本", placeholder: str = "在此处输入或粘贴内容...", mode: str = "translate"):
        super().__init__(parent)
        self.setObjectName("panelBox")
        self.setMinimumWidth(280)
        self.panel_title = title
        self.placeholder_text = placeholder
        self.mode = mode
        self.current_image: Optional[Image.Image] = None
        self._selected_span: Optional[SentenceSpan] = None
        self._is_programmatic_change = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 顶部标题区
        header_layout = QHBoxLayout()
        title = QLabel(self.panel_title)
        title.setObjectName("headerTitle")
        hint = QLabel("(双击逐句对照/整句复制，Ctrl+Enter 触发)")
        hint.setObjectName("statusLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(hint)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 图片预览卡片 (默认隐藏)
        self.preview_card = QFrame()
        self.preview_card.setObjectName("imagePreviewCard")
        preview_layout = QHBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(8, 4, 8, 4)
        preview_layout.setSpacing(10)

        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(56, 40)
        self.lbl_thumbnail.setScaledContents(True)
        preview_layout.addWidget(self.lbl_thumbnail)

        self.lbl_img_info = QLabel("📸 已载入待识别图片")
        self.lbl_img_info.setStyleSheet("font-size: 12px;")
        preview_layout.addWidget(self.lbl_img_info, 1)

        self.btn_remove_img = QPushButton("✕ 移除图片")
        self.btn_remove_img.setObjectName("secondaryBtn")
        self.btn_remove_img.setCursor(Qt.PointingHandCursor)
        self.btn_remove_img.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_remove_img.clicked.connect(self.clear_image)
        preview_layout.addWidget(self.btn_remove_img)

        self.preview_card.setVisible(False)
        layout.addWidget(self.preview_card)

        # 核心多行输入框
        self.editor = CustomInputEdit()
        self.editor.setPlaceholderText(self.placeholder_text)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.submit_triggered.connect(self._on_submit)
        self.editor.image_pasted.connect(self.set_image_from_qimage)
        self.editor.file_dropped.connect(self.set_image_from_path)
        self.editor.sentence_selected.connect(self._on_sentence_selected)
        self.editor.translate_sentence_requested.connect(self.translate_sentence_requested.emit)
        layout.addWidget(self.editor)

        # 底部双排对称操作栏
        footer_layout = QVBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(6)

        # 第 1 排：智能辅助与句级别操作排（左侧单句翻译，右侧同反义词与TTS朗读）
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.lbl_count = QLabel("字符数: 0")
        self.lbl_count.setObjectName("statusLabel")
        row1.addWidget(self.lbl_count)

        # 逐句对照中单句独立翻译专属快捷按钮 (始终展示，方便用户直接点击)
        self.btn_translate_sentence = QPushButton("🌐 单独翻译选定句")
        self.btn_translate_sentence.setObjectName("accentBtnSky")
        self.btn_translate_sentence.setCursor(Qt.PointingHandCursor)
        self.btn_translate_sentence.setToolTip("双击任意句子或将光标置于某句，点击此按钮可呼出单句独立翻译弹窗与微调替换")
        self.btn_translate_sentence.clicked.connect(self._on_translate_sentence_btn_clicked)
        row1.addWidget(self.btn_translate_sentence)

        row1.addStretch()

        # TTS 语音朗读按钮
        self.btn_tts = QPushButton("🔊 朗读")
        self.btn_tts.setObjectName("secondaryBtn")
        self.btn_tts.setCursor(Qt.PointingHandCursor)
        self.btn_tts.setToolTip("点击朗读当前文本 (再次点击停止)")
        self.btn_tts.clicked.connect(self._toggle_tts)
        row1.addWidget(self.btn_tts)

        footer_layout.addLayout(row1)

        # 第 2 排：基础操作与主行动排（左侧图片/粘贴/清空，右侧执行处理）
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_upload_img = QPushButton("🖼️ 上传图片")
        self.btn_upload_img.setObjectName("secondaryBtn")
        self.btn_upload_img.setCursor(Qt.PointingHandCursor)
        self.btn_upload_img.setToolTip("从本地选取图片进行 OCR 识别")
        self.btn_upload_img.clicked.connect(self._select_image_file)
        row2.addWidget(self.btn_upload_img)

        self.btn_paste = QPushButton("📋 粘贴")
        self.btn_paste.setObjectName("secondaryBtn")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self._paste_clipboard)
        row2.addWidget(self.btn_paste)

        self.btn_clear = QPushButton("🗑 清空")
        self.btn_clear.setObjectName("secondaryBtn")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_all)
        row2.addWidget(self.btn_clear)

        row2.addStretch()

        self.btn_submit = QPushButton(MODE_BUTTON_TEXTS.get(self.mode, "🚀 翻译"))
        self.btn_submit.setObjectName("primaryBtn")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.clicked.connect(self._on_submit)
        row2.addWidget(self.btn_submit)

        footer_layout.addLayout(row2)

        layout.addLayout(footer_layout)

        # 连接全局 TTS 停止信号同步按钮状态
        tts_manager.speech_finished.connect(self._on_tts_finished)

    def get_language(self) -> str:
        """Returns the current source language from control bar."""
        win = self.window()
        if win and hasattr(win, "control_bar"):
            return win.control_bar.get_languages()[0]
        return "Auto"

    def _toggle_tts(self):
        if tts_manager.is_speaking():
            tts_manager.stop()
            self.btn_tts.setText("🔊 朗读")
        else:
            text = self.get_text().strip()
            if text:
                tts_manager.speak(text, lang=self.get_language(), parent_widget=self)
                self.btn_tts.setText("⏹ 停止朗读")

    def _on_tts_finished(self):
        self.btn_tts.setText("🔊 朗读")

    def _on_sentence_selected(self, index: int, text: str, total: int):
        self._selected_span = SentenceSpan(index=index, text=text, start=0, end=len(text))
        self.btn_translate_sentence.setText(f"🌐 单独翻译此句 (第 {index + 1}/{total} 句)")
        self.sentence_selected.emit(index, text, total)

    def _on_translate_sentence_btn_clicked(self):
        if self._selected_span:
            self.translate_sentence_requested.emit(self._selected_span.index, self._selected_span.text)
        else:
            text = self.get_text().strip()
            if text:
                spans = split_sentences_with_spans(text)
                pos = self.editor.textCursor().position()
                span = find_sentence_at_position(spans, pos)
                if span:
                    self.editor.highlight_sentence(span.index)
                    self._selected_span = span
                    self.btn_translate_sentence.setText(f"🌐 单独翻译此句 (第 {span.index + 1}/{len(spans)} 句)")
                    self.translate_sentence_requested.emit(span.index, span.text)

    def highlight_sentence(self, index: int):
        """Highlights sentence in the editor."""
        self.editor.highlight_sentence(index)

    def clear_highlight(self):
        """Clears highlight and resets the single-sentence translate button text."""
        self.editor.clear_highlight()
        self.btn_translate_sentence.setText("🌐 单独翻译选定句")
        self._selected_span = None

    def _on_text_changed(self):
        count = len(self.editor.toPlainText())
        self.lbl_count.setText(f"字符数: {count}")
        self.clear_highlight()
        if not self._is_programmatic_change:
            self.user_text_changed.emit(self.editor.toPlainText())

    def _select_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要识别的图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*.*)"
        )
        if file_path:
            self.set_image_from_path(file_path)

    def set_image_from_path(self, file_path: str):
        try:
            pil_img = Image.open(file_path)
            self.current_image = pil_img
            pix = QPixmap(file_path)
            self._display_image_preview(pix, f"📸 {Path(file_path).name} ({pil_img.width}x{pil_img.height})")
        except Exception as e:
            print(f"Failed to load image from path {file_path}: {e}")

    def set_image_from_qimage(self, qimg: QImage):
        try:
            qbuf = QBuffer()
            qbuf.open(QBuffer.WriteOnly)
            qimg.save(qbuf, "PNG")
            raw_bytes = bytes(qbuf.data())
            qbuf.close()
            pil_img = Image.open(io.BytesIO(raw_bytes))
            self.current_image = pil_img
            pix = QPixmap.fromImage(qimg)
            self._display_image_preview(pix, f"📸 剪贴板截图 ({pil_img.width}x{pil_img.height})")
        except Exception as e:
            print(f"Failed to load pasted QImage: {e}")

    def _display_image_preview(self, pixmap: QPixmap, info_text: str):
        self.lbl_thumbnail.setPixmap(pixmap)
        self.lbl_img_info.setText(info_text)
        self.lbl_img_info.setStyleSheet("color: #E4E4E7; font-size: 12px;")
        self.preview_card.setVisible(True)
        self.btn_submit.setText("🔍 识别并处理 (Ctrl+Enter)")

    def set_ocr_warning(self, is_warning: bool, warning_text: str = ""):
        """Displays warning badge if current model lacks OCR capability."""
        if is_warning:
            self.lbl_img_info.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 12px;")
            self.lbl_img_info.setText(f"⚠️ {warning_text or '当前模型不支持 OCR 识图'}")
        else:
            self.lbl_img_info.setStyleSheet("color: #E4E4E7; font-size: 12px;")

    def update_submit_button_text(self):
        """Updates submit button text based on image preview and current mode."""
        if self.current_image:
            self.btn_submit.setText("🔍 识别并处理 (Ctrl+Enter)")
        else:
            self.btn_submit.setText(MODE_BUTTON_TEXTS.get(self.mode, "🚀 翻译"))

    def clear_image(self):
        self.current_image = None
        self.preview_card.setVisible(False)
        self.lbl_thumbnail.clear()
        self.update_submit_button_text()

    def _paste_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime:
            if mime.hasImage():
                img = clipboard.image()
                if not img.isNull():
                    self.set_image_from_qimage(img)
                    return
            if mime.hasUrls():
                for url in mime.urls():
                    f_path = url.toLocalFile()
                    if f_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                        self.set_image_from_path(f_path)
                        return
            text = clipboard.text()
            if text:
                self.editor.insertPlainText(text)
                self.editor.moveCursor(self.editor.textCursor().End)

    def _clear_all(self):
        self.editor.clear()
        self.clear_image()
        self.clear_highlight()
        self.editor.setFocus()

    def _on_submit(self):
        text = self.get_text().strip()
        if text or self.current_image:
            self.submit_requested.emit(text, self.current_image)

    def get_text(self) -> str:
        return self.editor.toPlainText()

    def set_text(self, text: str):
        self._is_programmatic_change = True
        try:
            self.editor.setPlainText(text)
        finally:
            self._is_programmatic_change = False

    def set_enabled(self, enabled: bool):
        self.btn_submit.setEnabled(enabled)

    def set_mode(self, mode: str):
        self.mode = mode
        self.update_submit_button_text()

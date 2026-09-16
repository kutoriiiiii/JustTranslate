# -*- coding: utf-8 -*-
"""Dialog for translating an individual sentence independently with streaming, alternative styles, and replacement options."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPlainTextEdit, QPushButton, QApplication,
    QFrame
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QTextCursor
from core.llm_client import LLMClient
from config.default_prompts import build_prompt_messages
from config.settings import settings

class SentenceTranslateWorker(QThread):
    token_received = Signal(str)
    completed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, llm_client: LLMClient, messages: list, temperature: float = 0.3):
        super().__init__()
        self.llm_client = llm_client
        self.messages = messages
        self.temperature = temperature
        self._is_aborted = False
        self._accumulated = ""

    def abort(self):
        self._is_aborted = True

    def run(self):
        try:
            generator = self.llm_client.stream_chat(self.messages, temperature=self.temperature)
            for token in generator:
                if self._is_aborted:
                    return
                self._accumulated += token
                self.token_received.emit(token)
            self.completed.emit(self._accumulated.strip())
        except Exception as e:
            self.error_occurred.emit(str(e))

class SentenceTranslateDialog(QDialog):
    """Dialog allowing users to inspect, re-translate, compare with original translation, and replace an individual sentence."""
    
    # Emits (sentence_index, new_translated_text)
    replace_requested = Signal(int, str)

    def __init__(
        self, 
        parent, 
        sentence_index: int, 
        sentence_text: str, 
        src_lang: str, 
        target_lang: str,
        profile: Dict[str, Any],
        current_target_text: str = "",
        eco_mode: bool = False
    ):
        super().__init__(parent)
        self.sentence_index = sentence_index
        self.sentence_text = sentence_text.strip()
        self.current_target_text = current_target_text.strip()
        self.src_lang = src_lang
        self.target_lang = target_lang
        self.profile = profile
        self.eco_mode = eco_mode
        self.worker: Optional[SentenceTranslateWorker] = None
        self._accumulated_result = ""

        self.setWindowTitle(f"🌐 单句独立翻译与对照微调 (第 {sentence_index + 1} 句) - Just Translate")
        self.setMinimumSize(580, 520)
        self._init_ui()
        # Automatically trigger translation on open
        self._start_translation(style="standard")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header Info
        header_layout = QHBoxLayout()
        lbl_info = QLabel(f"<b>语言对:</b> {self.src_lang} ➔ {self.target_lang}  |  <b>模型:</b> {self.profile.get('name', '默认')}")
        lbl_info.setStyleSheet("color: #38bdf8; font-size: 12px;")
        header_layout.addWidget(lbl_info)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 1. Source Sentence Area
        layout.addWidget(QLabel("<b>📖 原句内容 (可微调):</b>"))
        self.edit_source = QPlainTextEdit()
        self.edit_source.setPlainText(self.sentence_text)
        self.edit_source.setMaximumHeight(75)
        layout.addWidget(self.edit_source)

        # 2. Existing Translation in Output (for comparison)
        if self.current_target_text:
            layout.addWidget(QLabel("<b>📌 原有译文 (主面板当前已有内容):</b>"))
            self.lbl_existing = QLabel(self.current_target_text)
            self.lbl_existing.setWordWrap(True)
            self.lbl_existing.setObjectName("existingSentenceLabel")
            layout.addWidget(self.lbl_existing)

        # 3. Output Translation Area (Editable so user can directly modify before replace)
        layout.addWidget(QLabel("<b>💡 独立新译文 (生成后可自由编辑):</b>"))
        self.edit_output = QPlainTextEdit()
        self.edit_output.setPlaceholderText("正在等待生成单句译文...")
        layout.addWidget(self.edit_output, 1)

        # Status Label
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # 4. Variation & Alternative Style Buttons
        var_layout = QHBoxLayout()
        var_layout.addWidget(QLabel("<b>候选生成:</b>"))

        self.btn_var_standard = QPushButton("🎯 标准翻译")
        self.btn_var_standard.setObjectName("secondaryBtn")
        self.btn_var_standard.clicked.connect(lambda: self._start_translation(style="standard"))
        var_layout.addWidget(self.btn_var_standard)

        self.btn_var_natural = QPushButton("✨ 地道口语/自然")
        self.btn_var_natural.setObjectName("secondaryBtn")
        self.btn_var_natural.clicked.connect(lambda: self._start_translation(style="natural"))
        var_layout.addWidget(self.btn_var_natural)

        self.btn_var_creative = QPushButton("🎲 换一种表达 (高创造度)")
        self.btn_var_creative.setObjectName("secondaryBtn")
        self.btn_var_creative.setToolTip("以较高采样温度 (0.75) 尝试不同的词汇搭配与句式风格")
        self.btn_var_creative.clicked.connect(lambda: self._start_translation(style="creative"))
        var_layout.addWidget(self.btn_var_creative)

        var_layout.addStretch()
        layout.addLayout(var_layout)

        # 5. Bottom Action Buttons
        btn_bar = QHBoxLayout()

        self.btn_copy = QPushButton("📋 复制新译文")
        self.btn_copy.setObjectName("secondaryBtn")
        self.btn_copy.clicked.connect(self._copy_translation)
        btn_bar.addWidget(self.btn_copy)

        btn_bar.addStretch()

        self.btn_replace = QPushButton("🔄 替换到对应译文位置")
        self.btn_replace.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 16px; border-radius: 6px;")
        self.btn_replace.setToolTip("将主输出面板中该句的原有译文替换为上方编辑框中的新译文")
        self.btn_replace.clicked.connect(self._apply_replacement)
        btn_bar.addWidget(self.btn_replace)

        self.btn_close = QPushButton("✕ 关闭")
        self.btn_close.setObjectName("secondaryBtn")
        self.btn_close.clicked.connect(self.close)
        btn_bar.addWidget(self.btn_close)

        layout.addLayout(btn_bar)

    def _start_translation(self, style: str = "standard"):
        text_to_translate = self.edit_source.toPlainText().strip()
        if not text_to_translate:
            self.lbl_status.setText("原句内容为空，无法翻译")
            return

        if self.worker and self.worker.isRunning():
            self.worker.abort()
            self.worker.wait(500)

        self._accumulated_result = ""
        self.edit_output.clear()
        self.btn_replace.setEnabled(False)

        temperature = 0.3
        style_prompt = ""
        if style == "natural":
            style_prompt = "请使用更加地道、母语自然、符合口语与现代习惯的表达进行翻译，避免死板直译。"
            temperature = 0.5
            self.lbl_status.setText("正在以【地道自然】风格翻译本句...")
        elif style == "creative":
            style_prompt = "请使用不同的句式结构和丰富选词尝试一种全新的译法，提供耳目一新的翻译版本。"
            temperature = 0.75
            self.lbl_status.setText("正在以【换一种表达 (创造度 0.75)】生成全新候选...")
        else:
            self.lbl_status.setText("正在标准翻译本句...")

        client = LLMClient(
            base_url=self.profile.get("base_url", "http://127.0.0.1:8001/v1"),
            api_key=self.profile.get("api_key", ""),
            model=self.profile.get("model", ""),
            protocol=self.profile.get("protocol", "openai_chat"),
            provider=self.profile.get("id", ""),
            timeout=30.0,
            max_retries=settings.get("max_retries", 2)
        )

        custom_prompt = (
            f"你是一名专业翻译专家。请将用户提供的单句从【{self.src_lang}】翻译为【{self.target_lang}】。\n"
            f"{style_prompt}\n"
            f"严格要求：直接且仅输出翻译结果本身，绝对严禁添加引号、前缀说明或附言！"
        )

        messages = [
            {"role": "system", "content": custom_prompt},
            {"role": "user", "content": text_to_translate}
        ]

        self.worker = SentenceTranslateWorker(
            llm_client=client,
            messages=messages,
            temperature=temperature
        )
        self.worker.token_received.connect(self._on_token_received)
        self.worker.completed.connect(self._on_completed)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_token_received(self, token: str):
        self._accumulated_result += token
        self.edit_output.moveCursor(QTextCursor.End)
        self.edit_output.insertPlainText(token)
        self.edit_output.moveCursor(QTextCursor.End)

    def _on_completed(self, final_text: str):
        self._accumulated_result = final_text.strip()
        # 清理多余的外层引号
        if (self._accumulated_result.startswith('"') and self._accumulated_result.endswith('"')) or \
           (self._accumulated_result.startswith('“') and self._accumulated_result.endswith('”')):
            self._accumulated_result = self._accumulated_result[1:-1].strip()

        self.edit_output.setPlainText(self._accumulated_result)
        
        # 检查是否与原有译文完全一致
        if self.current_target_text and self._accumulated_result == self.current_target_text:
            self.lbl_status.setText("✓ 翻译完成（本次输出与原有译文一致，可点击「🎲 换一种表达」尝试新风格）")
        else:
            self.lbl_status.setText("✓ 翻译完成，可点击下方「替换」直接更新到主面板")
            
        self.btn_replace.setEnabled(bool(self._accumulated_result))

    def _on_error(self, err: str):
        self.lbl_status.setText(f"❌ 翻译失败: {err}")
        self.edit_output.setPlainText(f"翻译异常: {err}")
        self.btn_replace.setEnabled(False)

    def _copy_translation(self):
        text = self.edit_output.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            orig = self.btn_copy.text()
            self.btn_copy.setText("✓ 已复制")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy.setText(orig))

    def _apply_replacement(self):
        text = self.edit_output.toPlainText().strip()
        if text:
            self.replace_requested.emit(self.sentence_index, text)
            self.close()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.abort()
        super().closeEvent(event)

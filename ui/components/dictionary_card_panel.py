# -*- coding: utf-8 -*-
"""Native card-based Dictionary UI panel with responsive auto-wrapping layouts and in-place progressive card streaming."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QStackedWidget, QApplication, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QTimer

from core.dictionary_parser import parse_dictionary_output, DictionaryEntry, DefinitionItem, ExampleItem
from core.tts_manager import tts_manager
from ui.components.flow_layout import FlowLayout


class ResponsiveScrollArea(QScrollArea):
    """QScrollArea that keeps its inner container width strictly constrained to the viewport width."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        wid = self.widget()
        if wid and w > 0:
            wid.setMaximumWidth(w)


class DefinitionRow(QWidget):
    """Individual definition entry row with colored POS badge and wrapped dual-language meaning text."""

    def __init__(self, item: DefinitionItem, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        self.lbl_pos = QLabel(item.pos)
        self.lbl_pos.setObjectName("posBadge")
        self.lbl_pos.setAlignment(Qt.AlignCenter)
        self.lbl_pos.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lbl_pos.setVisible(bool(item.pos))
        layout.addWidget(self.lbl_pos, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.lbl_meaning = QLabel(item.meaning)
        self.lbl_meaning.setObjectName("dictDefText")
        self.lbl_meaning.setWordWrap(True)
        self.lbl_meaning.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_meaning.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_layout.addWidget(self.lbl_meaning)

        self.lbl_trans = QLabel(item.meaning_trans)
        self.lbl_trans.setObjectName("dictDefTrans")
        self.lbl_trans.setWordWrap(True)
        self.lbl_trans.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_trans.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_trans.setVisible(bool(item.meaning_trans))
        text_layout.addWidget(self.lbl_trans)

        layout.addLayout(text_layout, 1)

    def update_data(self, item: DefinitionItem):
        self.lbl_pos.setText(item.pos)
        self.lbl_pos.setVisible(bool(item.pos))
        self.lbl_meaning.setText(item.meaning)
        self.lbl_trans.setText(item.meaning_trans)
        self.lbl_trans.setVisible(bool(item.meaning_trans))


class ExampleBox(QFrame):
    """Individual bilingual example card with source, target translation, and anchored 🔊/📋 buttons."""

    def __init__(self, ex: ExampleItem, panel: "DictionaryCardPanel", parent=None):
        super().__init__(parent)
        self.setObjectName("dictExampleItemBox")
        self.panel = panel
        self.source_text = ex.source
        self.target_text = ex.target

        layout_single = QVBoxLayout(self)
        layout_single.setContentsMargins(8, 6, 8, 6)
        layout_single.setSpacing(4)

        # 顶部行：原句（自动折行、宽度自适应）+ 右侧常驻固定尺寸操作按钮
        row_top = QHBoxLayout()
        row_top.setContentsMargins(0, 0, 0, 0)
        row_top.setSpacing(6)

        self.lbl_src = QLabel(f"• {ex.source}")
        self.lbl_src.setObjectName("exampleSource")
        self.lbl_src.setWordWrap(True)
        self.lbl_src.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_src.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_top.addWidget(self.lbl_src, 1)

        self.btn_speak_ex = QPushButton("🔊")
        self.btn_speak_ex.setObjectName("dictActionBtn")
        self.btn_speak_ex.setToolTip("朗读该例句")
        self.btn_speak_ex.setCursor(Qt.PointingHandCursor)
        self.btn_speak_ex.setFixedSize(26, 24)
        self.btn_speak_ex.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_speak_ex.clicked.connect(lambda checked=False: self.panel._on_speak_example(self.source_text, self.btn_speak_ex))
        row_top.addWidget(self.btn_speak_ex)

        self.btn_copy_ex = QPushButton("📋")
        self.btn_copy_ex.setObjectName("dictActionBtn")
        self.btn_copy_ex.setToolTip("复制该例句")
        self.btn_copy_ex.setCursor(Qt.PointingHandCursor)
        self.btn_copy_ex.setFixedSize(26, 24)
        self.btn_copy_ex.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_copy_ex.clicked.connect(lambda checked=False: self.panel._on_copy_example(self.source_text, self.target_text, self.btn_copy_ex))
        row_top.addWidget(self.btn_copy_ex)

        layout_single.addLayout(row_top)

        self.lbl_tgt = QLabel(f"  {ex.target}" if ex.target else "")
        self.lbl_tgt.setObjectName("exampleTarget")
        self.lbl_tgt.setWordWrap(True)
        self.lbl_tgt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_tgt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_tgt.setVisible(bool(ex.target))
        layout_single.addWidget(self.lbl_tgt)

    def update_data(self, ex: ExampleItem):
        self.source_text = ex.source
        self.target_text = ex.target
        self.lbl_src.setText(f"• {ex.source}")
        self.lbl_tgt.setText(f"  {ex.target}" if ex.target else "")
        self.lbl_tgt.setVisible(bool(ex.target))


class DictionaryCardPanel(QFrame):
    """
    Structured native card dashboard for Dictionary lookups with in-place progressive streaming.
    
    Provides fixed, predictable positions for:
    - Headword, phonetics/kana, and instant 1-click TTS pronunciation (Flow-wrapped)
    - High-density definitions with compact colored POS badges (zero unnecessary line breaks)
    - Bilingual contextual examples with guaranteed visible quick copy/speak buttons
    - Collocations, synonyms, and antonyms chips with multi-line auto-wrapping FlowLayout
    """

    stop_requested = Signal()
    retry_requested = Signal()
    format_changed = Signal(str)
    sentence_selected = Signal(int, str, int)
    translate_sentence_requested = Signal(int, str)

    def __init__(self, parent=None, title: str = "词典释义与例句"):
        super().__init__(parent)
        self.setObjectName("panelBox")
        self.setMinimumWidth(280)
        self.panel_title = title
        self._raw_text = ""
        self._is_generating = False
        self._current_entry: Optional[DictionaryEntry] = None

        # 跟踪当前正在发音的按钮以提供动态交互特效
        self._active_tts_btn: Optional[QPushButton] = None
        self._active_tts_orig_text: str = ""
        self._active_tts_orig_tooltip: str = ""
        tts_manager.speech_finished.connect(self._on_tts_finished)

        # 流式节流定时器 (50ms，约 20 FPS)，确保渐进式流式填充平滑且不卡顿
        self._stream_timer = QTimer(self)
        self._stream_timer.setSingleShot(True)
        self._stream_timer.timeout.connect(self._on_stream_timer_tick)

        # 缓存子视图列表，便于原地增量更新
        self._def_rows: List[DefinitionRow] = []
        self._example_rows: List[ExampleBox] = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. 顶部标题与状态栏
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

        main_layout.addLayout(header_layout)

        # 2. 中间多视图堆栈：页面 0 为未查询初始占位；页面 1 为固定卡片看板模板
        self.stack = QStackedWidget()

        # 页面 0: 空白占位引导视图
        self.page_placeholder = QFrame()
        layout_ph = QVBoxLayout(self.page_placeholder)
        self.lbl_placeholder = QLabel("在此处输入词汇、短语或双语内容，点击【🔎 查询】查询权威词典...")
        self.lbl_placeholder.setObjectName("statusLabel")
        self.lbl_placeholder.setAlignment(Qt.AlignCenter)
        self.lbl_placeholder.setWordWrap(True)
        layout_ph.addStretch()
        layout_ph.addWidget(self.lbl_placeholder)
        layout_ph.addStretch()
        self.stack.addWidget(self.page_placeholder)

        # 页面 1: 固定词典卡片看板视图 (带视口宽度硬性约束与平滑滚动)
        self.page_cards = ResponsiveScrollArea()
        self.page_cards.setWidgetResizable(True)
        self.page_cards.setFrameShape(QFrame.NoFrame)
        self.page_cards.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_cards.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.page_cards.setWidget(self.cards_container)
        self.stack.addWidget(self.page_cards)

        # 构建常驻的词典看板卡片模板
        self._build_card_template()

        main_layout.addWidget(self.stack, 1)

        # 3. 底部操作栏
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(8)

        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("statusLabel")
        footer_layout.addWidget(self.lbl_info)

        footer_layout.addStretch()

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        footer_layout.addWidget(self.btn_stop)

        self.btn_retry = QPushButton("🔄 重试")
        self.btn_retry.setObjectName("secondaryBtn")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.clicked.connect(self.retry_requested.emit)
        footer_layout.addWidget(self.btn_retry)

        self.btn_copy_all = QPushButton("📋 复制释义")
        self.btn_copy_all.setObjectName("secondaryBtn")
        self.btn_copy_all.setCursor(Qt.PointingHandCursor)
        self.btn_copy_all.clicked.connect(self._copy_all_content)
        footer_layout.addWidget(self.btn_copy_all)

        main_layout.addLayout(footer_layout)

        # 初始显示占位页面
        self.stack.setCurrentIndex(0)

    def _build_card_template(self):
        """Constructs permanent native cards for in-place streaming."""
        # 异常提示卡片（默认隐藏）
        self.card_error = QFrame()
        self.card_error.setObjectName("dictCard")
        layout_err = QVBoxLayout(self.card_error)
        layout_err.setContentsMargins(10, 8, 10, 8)
        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        layout_err.addWidget(self.lbl_error)
        self.card_error.hide()
        self.cards_layout.addWidget(self.card_error)

        # 卡片 1：词头与发音卡片 (Header Card)
        self.card_header = QFrame()
        self.card_header.setObjectName("dictCard")
        self.layout_header = FlowLayout(self.card_header, margin=10, h_spacing=8, v_spacing=6)

        self.lbl_word = QLabel("词条解析")
        self.lbl_word.setObjectName("dictWordTitle")
        self.lbl_word.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.layout_header.addWidget(self.lbl_word)

        self.lbl_pron = QLabel("")
        self.lbl_pron.setObjectName("dictPron")
        self.lbl_pron.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_pron.hide()
        self.layout_header.addWidget(self.lbl_pron)

        self.btn_speak_word = QPushButton("🔊 朗读发音")
        self.btn_speak_word.setObjectName("dictHeaderBtn")
        self.btn_speak_word.setCursor(Qt.PointingHandCursor)
        self.btn_speak_word.setFixedHeight(26)
        self.btn_speak_word.clicked.connect(lambda checked=False: self._on_speak_word(self.lbl_word.text(), self.btn_speak_word))
        self.layout_header.addWidget(self.btn_speak_word)

        self.btn_copy_word = QPushButton("📋 复制词头")
        self.btn_copy_word.setObjectName("dictHeaderBtn")
        self.btn_copy_word.setCursor(Qt.PointingHandCursor)
        self.btn_copy_word.setFixedHeight(26)
        self.btn_copy_word.clicked.connect(lambda checked=False: self._on_copy_word(self.lbl_word.text(), self.btn_copy_word))
        self.layout_header.addWidget(self.btn_copy_word)

        self.cards_layout.addWidget(self.card_header)

        # 卡片 2：核心释义卡片 (Definitions Card)
        self.card_defs = QFrame()
        self.card_defs.setObjectName("dictCard")
        self.layout_defs = QVBoxLayout(self.card_defs)
        self.layout_defs.setContentsMargins(10, 8, 10, 8)
        self.layout_defs.setSpacing(6)

        self.title_defs = QLabel("📖 核心释义")
        self.title_defs.setObjectName("dictSectionTitle")
        self.layout_defs.addWidget(self.title_defs)

        self.lbl_defs_loading = QLabel("正在检索权威释义...")
        self.lbl_defs_loading.setObjectName("statusLabel")
        self.layout_defs.addWidget(self.lbl_defs_loading)

        self.defs_content_layout = QVBoxLayout()
        self.defs_content_layout.setContentsMargins(0, 0, 0, 0)
        self.defs_content_layout.setSpacing(6)
        self.layout_defs.addLayout(self.defs_content_layout)

        self.cards_layout.addWidget(self.card_defs)

        # 卡片 3：典型双语例句卡片 (Examples Card)
        self.card_examples = QFrame()
        self.card_examples.setObjectName("dictCard")
        self.layout_examples = QVBoxLayout(self.card_examples)
        self.layout_examples.setContentsMargins(10, 8, 10, 8)
        self.layout_examples.setSpacing(8)

        self.title_examples = QLabel("💡 典型双语例句")
        self.title_examples.setObjectName("dictSectionTitle")
        self.layout_examples.addWidget(self.title_examples)

        self.lbl_examples_loading = QLabel("正在生成典型双语例句...")
        self.lbl_examples_loading.setObjectName("statusLabel")
        self.layout_examples.addWidget(self.lbl_examples_loading)

        self.examples_content_layout = QVBoxLayout()
        self.examples_content_layout.setContentsMargins(0, 0, 0, 0)
        self.examples_content_layout.setSpacing(8)
        self.layout_examples.addLayout(self.examples_content_layout)

        self.cards_layout.addWidget(self.card_examples)

        # 卡片 4：搭配与近反义词标签卡片 (Collocations, Synonyms, Antonyms Card)
        self.card_extras = QFrame()
        self.card_extras.setObjectName("dictCard")
        self.layout_extras = QVBoxLayout(self.card_extras)
        self.layout_extras.setContentsMargins(10, 8, 10, 8)
        self.layout_extras.setSpacing(8)

        self.title_extras = QLabel("🔗 搭配与近反义词")
        self.title_extras.setObjectName("dictSectionTitle")
        self.layout_extras.addWidget(self.title_extras)

        # 搭配 FlowLayout 容器
        self.phrases_box = QWidget()
        self.phrases_layout = FlowLayout(self.phrases_box, margin=0, h_spacing=6, v_spacing=6)
        self.lbl_tag_p = QLabel("搭配:")
        self.lbl_tag_p.setObjectName("statusLabel")
        self.lbl_tag_p.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.phrases_layout.addWidget(self.lbl_tag_p)
        self.layout_extras.addWidget(self.phrases_box)
        self.phrases_box.hide()

        # 近义 FlowLayout 容器
        self.synonyms_box = QWidget()
        self.synonyms_layout = FlowLayout(self.synonyms_box, margin=0, h_spacing=6, v_spacing=6)
        self.lbl_tag_s = QLabel("近义:")
        self.lbl_tag_s.setObjectName("statusLabel")
        self.lbl_tag_s.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.synonyms_layout.addWidget(self.lbl_tag_s)
        self.layout_extras.addWidget(self.synonyms_box)
        self.synonyms_box.hide()

        # 反义 FlowLayout 容器
        self.antonyms_box = QWidget()
        self.antonyms_layout = FlowLayout(self.antonyms_box, margin=0, h_spacing=6, v_spacing=6)
        self.lbl_tag_a = QLabel("反义:")
        self.lbl_tag_a.setObjectName("statusLabel")
        self.lbl_tag_a.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.antonyms_layout.addWidget(self.lbl_tag_a)
        self.layout_extras.addWidget(self.antonyms_box)
        self.antonyms_box.hide()

        self.card_extras.hide()
        self.cards_layout.addWidget(self.card_extras)

        # 降级卡片（当模型彻底未遵循格式时的纯文本卡片）
        self.card_fallback = QFrame()
        self.card_fallback.setObjectName("dictCard")
        layout_fb = QVBoxLayout(self.card_fallback)
        layout_fb.setContentsMargins(10, 8, 10, 8)
        self.lbl_fallback = QLabel("")
        self.lbl_fallback.setObjectName("dictDefText")
        self.lbl_fallback.setWordWrap(True)
        self.lbl_fallback.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout_fb.addWidget(self.lbl_fallback)
        self.card_fallback.hide()
        self.cards_layout.addWidget(self.card_fallback)

        self.cards_layout.addStretch()

    def set_title(self, title: str):
        self.lbl_title.setText(title)

    def set_status(self, status: str):
        self.lbl_status.setText(status)

    def get_raw_text(self) -> str:
        return self._raw_text

    def set_target_language(self, lang: str):
        """Sets target language for standalone usage or testing."""
        self._target_lang = lang

    def get_output_language(self, text: str = "") -> str:
        """
        Determines the precise TTS language for content displayed in the dictionary output panel.
        Strictly follows the configured target language from the title/control bar.
        Never defaults to Chinese simply because text contains Han characters.
        """
        target_lang = getattr(self, "_target_lang", "Auto")
        win = self.window()
        if win and hasattr(win, "control_bar"):
            _, tgt = win.control_bar.get_languages()
            if tgt:
                target_lang = tgt

        # 严格按照标题栏的目标语言（只要设定了非 Auto 的具体目标语言）
        if target_lang and target_lang != "Auto":
            return target_lang

        # 仅当目标语言为 Auto 或未指定时，根据假名、注音与字符智能探测
        clean_text = text.strip().lstrip("•-* ")
        if clean_text and any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in clean_text):
            return "Japanese"

        pron = self.lbl_pron.text().strip()
        if pron and any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in pron):
            return "Japanese"

        if clean_text:
            return tts_manager.detect_language(clean_text)

        word = self.lbl_word.text().strip()
        if word and word not in ("词条解析", "正在查询..."):
            return tts_manager.detect_language(word)

        return "English"

    def get_language(self) -> str:
        """Compatibility wrapper for language queries."""
        return self.get_output_language()

    def start_streaming(self, query_word: str = ""):
        """Immediately displays fixed dictionary card template and prepares for progressive stream filling."""
        self._raw_text = ""
        self._is_generating = True
        self._current_entry = None
        self.btn_stop.setEnabled(True)
        self.btn_retry.setEnabled(False)

        win = self.window()
        if win and hasattr(win, "control_bar"):
            _, tgt = win.control_bar.get_languages()
            if tgt:
                self._target_lang = tgt

        # 立即切至卡片看板视图（消除任何原始文本框）
        self.stack.setCurrentIndex(1)
        self.lbl_status.setText("正在查询权威词典...")

        # 词头预填：若传入了待查词，微秒级在词头卡片展现待查词
        clean_q = query_word.strip()
        if clean_q:
            self.lbl_word.setText(clean_q)
            self.btn_copy_word.setEnabled(True)
            self.btn_speak_word.setEnabled(True)
        else:
            self.lbl_word.setText("正在查询...")
            self.btn_copy_word.setEnabled(False)
            self.btn_speak_word.setEnabled(False)

        self.lbl_pron.setText("")
        self.lbl_pron.hide()

        # 重置错误卡片
        self.card_error.hide()
        self.card_fallback.hide()

        # 重置释义卡片骨架
        self._clear_defs_content()
        self.lbl_defs_loading.setText("正在检索权威释义...")
        self.lbl_defs_loading.show()
        self.card_defs.show()

        # 重置例句卡片骨架
        self._clear_examples_content()
        self.lbl_examples_loading.setText("正在生成典型双语例句...")
        self.lbl_examples_loading.show()
        self.card_examples.show()

        # 重置搭配与近反义词
        self._clear_extras_chips()
        self.card_extras.hide()

    def append_chunk(self, chunk: str):
        """Appends streaming token chunk and triggers throttled progressive update."""
        self._raw_text += chunk
        if not self._stream_timer.isActive():
            self._stream_timer.start(50)

    def _on_stream_timer_tick(self):
        """Throttled progressive filling callback (20 FPS)."""
        if self._raw_text.strip():
            self._apply_progressive_update(is_final=False)

    def finish_streaming(self, final_text: str = None):
        """Finalizes progressive stream parsing and updates status to ready."""
        if self._stream_timer.isActive():
            self._stream_timer.stop()

        self._is_generating = False
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)

        if final_text is not None:
            self._raw_text = final_text

        text = self._raw_text.strip()
        if not text:
            self.stack.setCurrentIndex(0)
            self.lbl_status.setText("无结果")
            return

        self.stack.setCurrentIndex(1)
        self._apply_progressive_update(is_final=True)
        self.lbl_status.setText("就绪")

    def stop_streaming(self, partial_text: str = None):
        """Finalizes progressive stream parsing when cancelled/stopped by user, keeping partial results."""
        if self._stream_timer.isActive():
            self._stream_timer.stop()

        self._is_generating = False
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)

        if partial_text is not None:
            self._raw_text = partial_text

        text = self._raw_text.strip()
        if text:
            self.stack.setCurrentIndex(1)
            self._apply_progressive_update(is_final=True)
        self.lbl_status.setText("已停止")

    def set_stale_warning(self, visible: bool):
        """Displays or hides the amber stale warning badge."""
        self.lbl_stale_warning.setVisible(visible)

    def _apply_progressive_update(self, is_final: bool = False):
        """Incrementally parses LLM output and populates the fixed card template in-place."""
        entry = parse_dictionary_output(self._raw_text)
        self._current_entry = entry

        # 1. 更新词头与读音
        if entry.word:
            self.lbl_word.setText(entry.word)
            self.btn_copy_word.setEnabled(True)
            self.btn_speak_word.setEnabled(True)

        if entry.pronunciation:
            self.lbl_pron.setText(entry.pronunciation)
            self.lbl_pron.show()

        # 2. 原地增量更新释义
        if entry.definitions:
            self.lbl_defs_loading.hide()
            for i, item in enumerate(entry.definitions):
                if i < len(self._def_rows):
                    self._def_rows[i].update_data(item)
                else:
                    row = DefinitionRow(item, self.card_defs)
                    self._def_rows.append(row)
                    self.defs_content_layout.addWidget(row)
            # 清理多余释义控件（防止流式中间残留碎片）
            while len(self._def_rows) > len(entry.definitions):
                extra_row = self._def_rows.pop()
                self.defs_content_layout.removeWidget(extra_row)
                extra_row.deleteLater()
        else:
            self._clear_defs_content()
            if is_final:
                self.lbl_defs_loading.setText("（暂无释义）")
                self.lbl_defs_loading.show()

        # 3. 原地增量更新例句
        if entry.examples:
            self.lbl_examples_loading.hide()
            for i, ex in enumerate(entry.examples):
                if i < len(self._example_rows):
                    self._example_rows[i].update_data(ex)
                else:
                    box = ExampleBox(ex, self, self.card_examples)
                    self._example_rows.append(box)
                    self.examples_content_layout.addWidget(box)
            # 清理多余例句控件（防止流式中间残留如 • [PH 碎片）
            while len(self._example_rows) > len(entry.examples):
                extra_box = self._example_rows.pop()
                self.examples_content_layout.removeWidget(extra_box)
                extra_box.deleteLater()
        else:
            self._clear_examples_content()
            if is_final:
                self.lbl_examples_loading.setText("（暂无例句）")
                self.lbl_examples_loading.show()

        # 4. 原地增量更新搭配与近反义词
        has_extras = bool(entry.phrases or entry.synonyms or entry.antonyms)
        if has_extras:
            self.card_extras.show()
            self._update_flow_chips(self.phrases_box, self.phrases_layout, "chipBlue", entry.phrases)
            self._update_flow_chips(self.synonyms_box, self.synonyms_layout, "chipEmerald", entry.synonyms)
            self._update_flow_chips(self.antonyms_box, self.antonyms_layout, "chipAmber", entry.antonyms)
        elif is_final:
            self.card_extras.hide()

        # 5. 降级备用纯文本卡片（仅当完全无结构化内容时）
        if not entry.definitions and not entry.examples and entry.raw_text and not entry.is_structured:
            self.card_fallback.show()
            self.lbl_fallback.setText(entry.raw_text)
        else:
            self.card_fallback.hide()

    def _clear_defs_content(self):
        """Clears definition rows without deleting outer card."""
        while self.defs_content_layout.count():
            item = self.defs_content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._def_rows.clear()

    def _clear_examples_content(self):
        """Clears example boxes without deleting outer card."""
        self._reset_active_tts_btn()
        while self.examples_content_layout.count():
            item = self.examples_content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._example_rows.clear()

    def _clear_extras_chips(self):
        """Clears chip widgets from FlowLayouts while keeping section label."""
        for box, flow in [(self.phrases_box, self.phrases_layout), 
                          (self.synonyms_box, self.synonyms_layout), 
                          (self.antonyms_box, self.antonyms_layout)]:
            # flow item 0 is the tag label ("搭配:", "近义:", "反义:")
            while flow.count() > 1:
                item = flow.takeAt(1)
                w = item.widget()
                if w:
                    w.deleteLater()
            box.hide()

    def _update_flow_chips(self, container: QWidget, flow: FlowLayout, chip_style: str, items: List[str]):
        """Updates or appends chip labels in a FlowLayout."""
        if not items:
            container.hide()
            return

        container.show()
        # 获取现有 chips (item 0 是 tag 标签)
        existing_chips = []
        for i in range(1, flow.count()):
            item = flow.itemAt(i)
            if item and item.widget():
                existing_chips.append(item.widget())

        for i, text in enumerate(items):
            if i < len(existing_chips):
                existing_chips[i].setText(text)
                existing_chips[i].show()
            else:
                c = QLabel(text)
                c.setObjectName(chip_style)
                c.setTextInteractionFlags(Qt.TextSelectableByMouse)
                flow.addWidget(c)

        # 隐藏多余的 chips
        for i in range(len(items), len(existing_chips)):
            existing_chips[i].hide()

    def _on_speak_word(self, word: str, btn: QPushButton):
        """Handles word speech synthesis with interactive state toggling."""
        clean_word = word.strip()
        if not clean_word or clean_word in ["词条解析", "正在查询..."]:
            return

        if self._active_tts_btn == btn and tts_manager._is_speaking:
            tts_manager.stop()
            self._reset_active_tts_btn()
            return

        self._reset_active_tts_btn()
        self._active_tts_btn = btn
        self._active_tts_orig_text = btn.text()
        self._active_tts_orig_tooltip = btn.toolTip()
        self._active_tts_orig_style = btn.styleSheet()

        btn.setText("⏹ 停止朗读")
        btn.setToolTip("正在朗读发音，点击停止")
        btn.setStyleSheet("color: #38BDF8; font-weight: 600;")

        lang = self.get_output_language(clean_word)
        tts_manager.speak(clean_word, lang=lang, parent_widget=self)

    def _on_copy_word(self, word: str, btn: QPushButton):
        """Copies word head to clipboard with visual confirmation."""
        clean_word = word.strip()
        if not clean_word or clean_word in ["词条解析", "正在查询..."]:
            return
        QApplication.clipboard().setText(clean_word)
        orig_text = btn.text()
        orig_tooltip = btn.toolTip()
        orig_style = btn.styleSheet()
        btn.setText("✓ 已复制")
        btn.setStyleSheet("color: #10B981; font-weight: 600;")
        QTimer.singleShot(1500, lambda: self._safe_restore_btn(btn, orig_text, orig_style, orig_tooltip))

    def _on_speak_example(self, text: str, btn: QPushButton):
        """Speaks example sentence with active soundwave animation indicator."""
        clean_text = text.strip().lstrip("•-* ")
        if not clean_text:
            return

        if self._active_tts_btn == btn and tts_manager._is_speaking:
            tts_manager.stop()
            self._reset_active_tts_btn()
            return

        self._reset_active_tts_btn()
        self._active_tts_btn = btn
        self._active_tts_orig_text = btn.text()
        self._active_tts_orig_tooltip = btn.toolTip()
        self._active_tts_orig_style = btn.styleSheet()

        btn.setText("🔊...")
        btn.setToolTip("正在朗读中，点击停止")
        btn.setStyleSheet("color: #38BDF8; font-weight: bold; border-color: rgba(56, 189, 248, 0.5);")

        lang = self.get_output_language(clean_text)
        tts_manager.speak(clean_text, lang=lang, parent_widget=self)

    def _on_copy_example(self, source: str, target: str, btn: QPushButton):
        """Copies example bilingual pair with instant checkmark feedback."""
        s = source.strip().lstrip("•-* ")
        t = target.strip()
        content = f"{s}\n{t}" if t else s
        if not content:
            return

        QApplication.clipboard().setText(content)
        orig_text = btn.text()
        orig_tooltip = btn.toolTip()
        orig_style = btn.styleSheet()

        btn.setText("✓")
        btn.setToolTip("已复制到剪贴板！")
        btn.setStyleSheet("color: #10B981; font-weight: bold; border-color: rgba(16, 185, 129, 0.5);")

        QTimer.singleShot(1500, lambda: self._safe_restore_btn(btn, orig_text, orig_style, orig_tooltip))

    def _safe_restore_btn(self, btn: QPushButton, text: str, stylesheet: str = "", tooltip: str = ""):
        """Safely restores button label and stylesheet without throwing if widget was destroyed."""
        try:
            if btn and not btn.isHidden():
                btn.setText(text)
                btn.setStyleSheet(stylesheet)
                if tooltip:
                    btn.setToolTip(tooltip)
        except RuntimeError:
            pass

    def _on_tts_finished(self):
        """Restores active speech button state when audio finishes or is stopped."""
        self._reset_active_tts_btn()

    def _reset_active_tts_btn(self):
        """Resets active speech button to its idle appearance."""
        if self._active_tts_btn:
            try:
                self._active_tts_btn.setText(self._active_tts_orig_text)
                self._active_tts_btn.setToolTip(self._active_tts_orig_tooltip)
                self._active_tts_btn.setStyleSheet(getattr(self, "_active_tts_orig_style", ""))
            except RuntimeError:
                pass
            self._active_tts_btn = None

    def _copy_all_content(self):
        """Copies formatted dictionary entry to clipboard."""
        copied = False
        if self._current_entry:
            lines = []
            if self._current_entry.word:
                lines.append(f"{self._current_entry.word} {self._current_entry.pronunciation}".strip())
                lines.append("")
            if self._current_entry.definitions:
                lines.append("【核心释义】")
                for item in self._current_entry.definitions:
                    if item.meaning_trans:
                        lines.append(f"{item.pos} {item.meaning} | {item.meaning_trans}".strip())
                    else:
                        lines.append(f"{item.pos} {item.meaning}".strip())
                lines.append("")
            if self._current_entry.examples:
                lines.append("【典型例句】")
                for ex in self._current_entry.examples:
                    lines.append(f"• {ex.source}")
                    if ex.target:
                        lines.append(f"  {ex.target}")
                lines.append("")
            if self._current_entry.phrases:
                lines.append(f"【常用搭配】 {', '.join(self._current_entry.phrases)}")
            if self._current_entry.synonyms:
                lines.append(f"【同义词】 {', '.join(self._current_entry.synonyms)}")
            if self._current_entry.antonyms:
                lines.append(f"【反义词】 {', '.join(self._current_entry.antonyms)}")

            full_text = "\n".join(lines).strip()
            if full_text:
                QApplication.clipboard().setText(full_text)
                copied = True

        if not copied and self._raw_text.strip():
            QApplication.clipboard().setText(self._raw_text.strip())
            copied = True

        if copied:
            orig = self.btn_copy_all.text()
            self.btn_copy_all.setText("✓ 已复制释义")
            self.btn_copy_all.setStyleSheet("color: #10B981; font-weight: 600;")
            QTimer.singleShot(1500, lambda: self._safe_restore_btn(self.btn_copy_all, orig, ""))

    def show_error(self, error_msg: str):
        """Displays error message cleanly inside an error card banner."""
        self._is_generating = False
        if self._stream_timer.isActive():
            self._stream_timer.stop()
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(True)
        self.lbl_status.setText("出错了")

        self.stack.setCurrentIndex(1)
        self.lbl_error.setText(f"❌ 词典查询失败：\n{error_msg}")
        self.lbl_error.setStyleSheet("color: #EF4444; font-weight: 600; font-size: 13px;")
        self.card_error.show()

    def replace_sentence_at_index(self, index: int, text: str):
        """Compatibility method for sentence replacement."""
        pass

    def set_format(self, fmt: str):
        """Compatibility method with MainWindow format synchronization."""
        pass

    def highlight_sentence(self, index: int):
        """Compatibility method with cross-box sentence alignment."""
        pass

    def clear_highlight(self):
        """Compatibility method to clear highlights."""
        pass

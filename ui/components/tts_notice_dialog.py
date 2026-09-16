# -*- coding: utf-8 -*-
"""Dialog explaining missing local Windows voice pack and online Edge TTS fallback with 'don't remind again' option."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from config.settings import settings


class TTSNoticeDialog(QDialog):
    """Gentle, user-friendly prompt shown when a target language lacks a local Windows voice pack."""

    def __init__(self, lang_name: str, parent=None):
        super().__init__(parent)
        self.lang_name = lang_name
        self.setWindowTitle("语音包提示 - Just Translate")
        self.setMinimumWidth(440)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题栏
        lbl_title = QLabel("💡 离线语音包与在线朗读提示")
        lbl_title.setObjectName("headerTitle")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(lbl_title)

        # 详细提示说明卡片
        info_card = QFrame()
        info_card.setObjectName("panelBox")
        card_layout = QVBoxLayout(info_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        msg_html = (
            f"<div style='line-height: 1.6; font-size: 13px;'>"
            f"检测到当前系统尚未预装<b>【{self.lang_name}】</b>的 Windows 本地离线语音包。<br><br>"
            f"软件现已自动启用<b>微软 Edge 高质量神经语音</b>为您在线朗读。<br><br>"
            f"<b>💡 如何在 Windows 中添加离线语音包：</b><br>"
            f"1. 打开 Windows <b>设置</b> (快捷键 Win + I)；<br>"
            f"2. 点击 <b>时间和语言</b> ➔ <b>语音</b> (或 <b>语言和区域</b>)；<br>"
            f"3. 点击 <b>“添加语音”</b>，勾选下载【{self.lang_name}】语音包即可。<br><br>"
            f"<span style='color: #64748B; font-size: 12px;'>提示：安装本地语音包后，您即可在断网或离线环境中继续朗读。</span>"
            f"</div>"
        )
        lbl_info = QLabel(msg_html)
        lbl_info.setWordWrap(True)
        lbl_info.setTextFormat(Qt.RichText)
        card_layout.addWidget(lbl_info)

        layout.addWidget(info_card)

        # 以后不再提醒选择框
        self.check_dont_remind = QCheckBox("以后不再提醒（默认直接使用高质量在线语音）")
        self.check_dont_remind.setCursor(Qt.PointingHandCursor)
        self.check_dont_remind.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.check_dont_remind)

        # 底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_continue = QPushButton("继续朗读")
        self.btn_continue.setObjectName("primaryBtn")
        self.btn_continue.setCursor(Qt.PointingHandCursor)
        self.btn_continue.clicked.connect(self._on_continue)
        btn_layout.addWidget(self.btn_continue)

        layout.addLayout(btn_layout)

    def _on_continue(self):
        if self.check_dont_remind.isChecked():
            settings.set("tts_suppress_missing_voice_dialog", True)
            settings.save()
        self.accept()

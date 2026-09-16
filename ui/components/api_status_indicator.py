# -*- coding: utf-8 -*-
"""Real-time API connection status, latency (TTFT / ping), and generation speed (tok/s) indicator."""

import time
import urllib.request
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCursor
from core.network_utils import open_url_respecting_proxy

class PingWorker(QThread):
    """Lightweight background thread to ping the model endpoint without blocking UI."""
    ping_result = Signal(bool, int, str)

    def __init__(self, base_url: str, api_key: str = ""):
        super().__init__()
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()

    def run(self):
        t0 = time.time()
        url = self.base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[:-17].rstrip("/")
        if not url.endswith("/models"):
            url += "/models"
        try:
            req = urllib.request.Request(url, method="GET")
            if self.api_key and self.api_key not in ("sk-no-key", "ollama"):
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with open_url_respecting_proxy(req, timeout=3.0) as resp:
                _ = resp.read(1024)
            latency_ms = max(1, int((time.time() - t0) * 1000))
            self.ping_result.emit(True, latency_ms, "")
        except Exception as e:
            err = str(e)
            self.ping_result.emit(False, 0, err)

class ApiStatusIndicator(QFrame):
    """Capsule widget displaying connection status (dot), latency (ms), and generation speed (tok/s)."""

    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusIndicator")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip("\u70b9\u51fb\u5237\u65b0 API \u8fde\u63a5\u72b6\u6001\u4e0e\u54cd\u5e94\u5ef6\u8fdf")

        self.last_latency = 0
        self.last_speed = 0.0
        self.ping_worker = None

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 状态指示圆点
        self.lbl_dot = QLabel("\u25cf")
        self.lbl_dot.setStyleSheet("color: #10B981; font-size: 11px;")
        layout.addWidget(self.lbl_dot)

        # 延迟标签
        self.lbl_latency = QLabel("-- ms")
        self.lbl_latency.setObjectName("statusLatency")
        layout.addWidget(self.lbl_latency)

        # 分割竖线
        self.lbl_sep = QLabel("|")
        self.lbl_sep.setObjectName("statusSep")
        layout.addWidget(self.lbl_sep)

        # 速度标签
        self.lbl_speed = QLabel("-- tok/s")
        self.lbl_speed.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.lbl_speed)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.refresh_requested.emit()
        super().mousePressEvent(event)

    def set_connecting(self):
        self.lbl_dot.setStyleSheet("color: #FBBF24; font-size: 11px;")
        self.lbl_latency.setText("\u8fde\u63a5\u4e2d...")
        self.lbl_speed.setText("-- tok/s")

    def set_streaming(self, latency_ms: int, speed_tok_s: float):
        self.lbl_dot.setStyleSheet("color: #FBBF24; font-size: 11px;")
        self.last_latency = latency_ms
        self.last_speed = speed_tok_s
        self.lbl_latency.setText(f"{latency_ms} ms")
        self.lbl_speed.setText(f"{speed_tok_s:.1f} tok/s")

    def set_ready(self, latency_ms: int = None, speed_tok_s: float = None):
        self.lbl_dot.setStyleSheet("color: #10B981; font-size: 11px;")
        if latency_ms is not None and latency_ms > 0:
            self.last_latency = latency_ms
            self.lbl_latency.setText(f"{latency_ms} ms")
        elif self.last_latency > 0:
            self.lbl_latency.setText(f"{self.last_latency} ms")
        else:
            self.lbl_latency.setText("\u5c31\u7eea")

        if speed_tok_s is not None and speed_tok_s > 0:
            self.last_speed = speed_tok_s
            self.lbl_speed.setText(f"{speed_tok_s:.1f} tok/s")
        elif self.last_speed > 0:
            self.lbl_speed.setText(f"{self.last_speed:.1f} tok/s")
        else:
            self.lbl_speed.setText("-- tok/s")

    def set_error(self, err_msg: str = ""):
        self.lbl_dot.setStyleSheet("color: #EF4444; font-size: 11px;")
        self.lbl_latency.setText("\u8fde\u63a5\u5f02\u5e38")
        self.lbl_speed.setText("-- tok/s")
        if err_msg:
            self.setToolTip(f"API \u8fde\u63a5\u5f02\u5e38: {err_msg}\n\u70b9\u51fb\u91cd\u8bd5")

    def check_connection(self, base_url: str, api_key: str = ""):
        if not base_url:
            self.set_error("\u672a\u914d\u7f6e Base URL")
            return

        if self.ping_worker and self.ping_worker.isRunning():
            self.ping_worker.terminate()
            self.ping_worker.wait(200)

        self.lbl_dot.setStyleSheet("color: #FBBF24; font-size: 11px;")
        self.lbl_latency.setText("\u68c0\u6d4b\u4e2d...")

        self.ping_worker = PingWorker(base_url, api_key)
        self.ping_worker.ping_result.connect(self._on_ping_result)
        self.ping_worker.start()

    def _on_ping_result(self, success: bool, latency_ms: int, error_msg: str):
        if success:
            self.set_ready(latency_ms=latency_ms)
            self.setToolTip(f"API \u8fde\u63a5\u6b63\u5e38\n\u57fa\u51c6\u54cd\u5e94\u5ef6\u8fdf: {latency_ms} ms\n\u70b9\u51fb\u91cd\u65b0\u68c0\u6d4b")
        else:
            self.set_error(error_msg)

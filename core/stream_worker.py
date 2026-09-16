# -*- coding: utf-8 -*-
"""Stream worker thread based on PySide6 QThread."""

from PySide6.QtCore import QThread, Signal
from typing import List, Dict
from .llm_client import LLMClient
from .network_utils import StreamController

class StreamWorker(QThread):
    """Worker thread that executes LLM streaming without blocking GUI."""

    token_received = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)
    completed = Signal(str)
    stopped = Signal(str)
    metrics_updated = Signal(int, float)
    metrics_completed = Signal(int, float)

    def __init__(self, client: LLMClient, messages: List[Dict[str, str]], temperature: float = 0.3):
        super().__init__()
        self.client = client
        self.messages = messages
        self.temperature = temperature
        self._is_aborted = False
        self._accumulated_text = ""
        self.controller = StreamController()

    def abort(self):
        """Forcibly interrupts the active network stream and stops the worker immediately."""
        self._is_aborted = True
        self.controller.abort()

    def run(self):
        self.status_changed.emit("正在请求模型并建立连接...")
        try:
            import time
            t_req_start = time.time()
            generator = self.client.stream_chat(
                self.messages, 
                temperature=self.temperature, 
                controller=self.controller
            )
            first_token = True
            t_first_token = None
            token_count = 0
            latency_ms = 0

            for token in generator:
                if self._is_aborted:
                    self.status_changed.emit("已停止")
                    self.stopped.emit(self._accumulated_text)
                    return

                now = time.time()
                if first_token:
                    t_first_token = now
                    latency_ms = max(1, int((t_first_token - t_req_start) * 1000))
                    self.status_changed.emit("正在流式生成...")
                    first_token = False

                token_count += 1
                self._accumulated_text += token
                self.token_received.emit(token)

                elapsed = now - t_first_token
                if elapsed > 0.05:
                    current_speed = token_count / elapsed
                    self.metrics_updated.emit(latency_ms, current_speed)

            if self._is_aborted:
                self.status_changed.emit("已停止")
                self.stopped.emit(self._accumulated_text)
                return

            total_time = time.time() - (t_first_token or t_req_start)
            final_speed = token_count / total_time if total_time > 0 else 0.0
            self.metrics_completed.emit(latency_ms, final_speed)
            self.status_changed.emit("生成完成")
            self.completed.emit(self._accumulated_text)

        except Exception as e:
            if self._is_aborted:
                self.status_changed.emit("已停止")
                self.stopped.emit(self._accumulated_text)
            else:
                self.error_occurred.emit(str(e))
                self.status_changed.emit("生成出错")

# -*- coding: utf-8 -*-
"""Pipeline worker orchestrating OCR text recognition and LLM streaming translation."""

from typing import Optional, List, Dict, Union
from PIL import Image
from PySide6.QtCore import QThread, Signal
from .llm_client import LLMClient
from .ocr_client import OCRClient
from .network_utils import StreamController

class PipelineWorker(QThread):
    """Two-stage worker: OCR extraction followed by streaming LLM translation/polishing."""

    ocr_text_extracted = Signal(str)
    token_received = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)
    completed = Signal(str)
    stopped = Signal(str)
    metrics_updated = Signal(int, float)
    metrics_completed = Signal(int, float)

    def __init__(
        self,
        llm_client: LLMClient,
        messages_builder_fn,
        image_input: Optional[Union[bytes, str, Image.Image]] = None,
        ocr_client: Optional[OCRClient] = None,
        raw_text: str = "",
        temperature: float = 0.3
    ):
        super().__init__()
        self.llm_client = llm_client
        self.messages_builder_fn = messages_builder_fn
        self.image_input = image_input
        self.ocr_client = ocr_client
        self.raw_text = raw_text
        self.temperature = temperature
        self._is_aborted = False
        self._accumulated_text = ""
        self.controller = StreamController()

    def abort(self):
        """Signals the worker and forcibly closes active sockets/requests immediately."""
        self._is_aborted = True
        self.controller.abort()

    def run(self):
        try:
            text_to_process = self.raw_text

            # 第一阶段：若存在图片，先执行 OCR 识别
            if self.image_input and self.ocr_client:
                self.status_changed.emit("正在调用 GLM-OCR 识别图片文字...")
                extracted = self.ocr_client.recognize_text(
                    self.image_input,
                    controller=self.controller
                )

                if self._is_aborted:
                    self.status_changed.emit("已停止")
                    self.stopped.emit("")
                    return

                if not extracted or not extracted.strip():
                    self.error_occurred.emit("未能在图片中识别出任何文字内容")
                    self.status_changed.emit("识别未提取到文字")
                    return

                text_to_process = extracted.strip()
                # 发出提取到的文字，以便主界面回填输入框
                self.ocr_text_extracted.emit(text_to_process)

            if self._is_aborted:
                self.status_changed.emit("已停止")
                self.stopped.emit("")
                return

            # 第二阶段：联动翻译 / 润色 / 词典
            messages = self.messages_builder_fn(text_to_process)
            self.status_changed.emit("正在连接翻译模型并流式生成...")

            import time
            t_req_start = time.time()
            generator = self.llm_client.stream_chat(
                messages, 
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
                self.status_changed.emit("执行出错")

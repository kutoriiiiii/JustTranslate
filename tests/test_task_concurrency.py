# -*- coding: utf-8 -*-
"""Unit tests for task concurrency, task ID signal filtering, and safe stopping."""

import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from core.stream_worker import StreamWorker
from core.pipeline_worker import PipelineWorker
from ui.components.output_panel import OutputPanel

app = QApplication.instance() or QApplication([])

class TestTaskConcurrency(unittest.TestCase):
    """Verifies task ID routing, signal isolation, and stopping semantics."""

    def test_task_id_signal_filtering(self):
        current_task_id = 2
        received_chunks = []

        def handle_chunk(chunk: str, tid: int):
            if tid != current_task_id:
                return
            received_chunks.append(chunk)

        # Signals from old task (tid=1) must be ignored
        handle_chunk("old task chunk", 1)
        self.assertEqual(len(received_chunks), 0)

        # Signal from current task (tid=2) must be received
        handle_chunk("new task chunk", 2)
        self.assertEqual(received_chunks, ["new task chunk"])

        # If user submits again and task_id increments to 3, signals with tid=2 must be ignored
        current_task_id = 3
        handle_chunk("late chunk from tid 2", 2)
        self.assertEqual(received_chunks, ["new task chunk"])

    def test_stream_worker_abort_emits_stopped_not_completed(self):
        mock_client = MagicMock()
        # Mock a slow generator that yields tokens
        def slow_tokens(*args, **kwargs):
            yield "token1"
            yield "token2"

        mock_client.stream_chat.return_value = slow_tokens()
        worker = StreamWorker(client=mock_client, messages=[{"role": "user", "content": "hi"}])
        
        stopped_payloads = []
        completed_payloads = []
        error_payloads = []

        worker.stopped.connect(lambda txt: stopped_payloads.append(txt))
        worker.completed.connect(lambda txt: completed_payloads.append(txt))
        worker.error_occurred.connect(lambda err: error_payloads.append(err))

        # Abort worker before/during run
        worker.abort()
        worker.run()

        # Must emit stopped and MUST NOT emit completed or error
        self.assertEqual(len(stopped_payloads), 1)
        self.assertEqual(len(completed_payloads), 0)
        self.assertEqual(len(error_payloads), 0)

    def test_output_panel_stop_streaming_preserves_partial_text(self):
        panel = OutputPanel(title="译文")
        panel.start_streaming()
        panel.append_chunk("Partially generated translation...")
        self.assertEqual(panel.get_raw_text(), "Partially generated translation...")

        panel.stop_streaming()
        self.assertEqual(panel.lbl_status.text(), "已停止")
        # Content must be preserved for user viewing
        self.assertEqual(panel.get_raw_text(), "Partially generated translation...")
        self.assertFalse(panel.btn_stop.isEnabled())
        self.assertTrue(panel.btn_retry.isEnabled())

if __name__ == "__main__":
    unittest.main()

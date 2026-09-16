# -*- coding: utf-8 -*-
"""Integration tests verifying full user workflows for all 4 new requirements."""

import os
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.network_utils import create_httpx_client
from core.history_manager import history_manager

app = QApplication.instance() or QApplication([])

class TestIntegrationUserFlows(unittest.TestCase):
    """End-to-end integration tests for MainWindow workflows."""

    def setUp(self):
        self.worker_patcher = patch("core.pipeline_worker.PipelineWorker.start")
        self.mock_worker_start = self.worker_patcher.start()
        self.window = MainWindow()

    def tearDown(self):
        self.window._is_quitting = True
        if hasattr(self.window, "tray_icon") and self.window.tray_icon:
            self.window.tray_icon.hide()
        self.window.close()
        self.worker_patcher.stop()

    def test_mode_button_texts_on_mode_switch(self):
        # 1. Default mode: translate -> 🚀 翻译
        in_p_tr = self.window.input_panels["translate"]
        self.assertEqual(in_p_tr.btn_submit.text(), "🚀 翻译")

        # 2. Switch to polish -> ✨ 润色
        self.window.control_bar.set_mode("polish", emit_signal=True)
        in_p_pol = self.window.input_panels["polish"]
        self.assertEqual(in_p_pol.btn_submit.text(), "✨ 润色")

        # 3. Switch to dictionary -> 🔎 查询
        self.window.control_bar.set_mode("dictionary", emit_signal=True)
        in_p_dict = self.window.input_panels["dictionary"]
        self.assertEqual(in_p_dict.btn_submit.text(), "🔎 查询")

    def test_stale_warning_lifecycle_on_source_edits(self):
        mode = "translate"
        in_p = self.window.input_panels[mode]
        out_p = self.window.output_panels[mode]

        # 1. Start generation for 'First Draft'
        in_p.set_text("First Draft")
        self.window._start_generation("First Draft", mode)
        self.assertTrue(out_p.lbl_stale_warning.isHidden())
        self.assertEqual(self.window._request_snapshots[mode], "First Draft")

        # 2. While generating (or after), user edits text
        in_p.editor.insertPlainText(" with changes")
        # _on_user_text_changed is called
        self.assertFalse(out_p.lbl_stale_warning.isHidden())

        # 3. Old generation finishes: stale warning must persist because input differs from snapshot
        tid = self.window._current_task_ids[mode]
        self.window._handle_worker_completed("Translated first draft", mode, tid)
        self.assertFalse(out_p.lbl_stale_warning.isHidden())

        # 4. User starts new generation with current text: stale warning is cleared!
        new_text = in_p.get_text()
        self.window._start_generation(new_text, mode)
        self.assertTrue(out_p.lbl_stale_warning.isHidden())

        # 5. New generation completes without edits: stale warning stays hidden
        tid2 = self.window._current_task_ids[mode]
        self.window._handle_worker_completed("Translated new text", mode, tid2)
        self.assertTrue(out_p.lbl_stale_warning.isHidden())

    def test_concurrency_rapid_submissions_isolate_signals(self):
        mode = "translate"
        out_p = self.window.output_panels[mode]

        # Request 1
        self.window._start_generation("Request 1", mode)
        tid1 = self.window._current_task_ids[mode]

        # Rapidly trigger Request 2
        self.window._start_generation("Request 2", mode)
        tid2 = self.window._current_task_ids[mode]
        self.assertEqual(tid2, tid1 + 1)

        # Worker from Request 1 sends token -> MUST BE DROPPED
        self.window._handle_worker_token("Chunk from old task 1", mode, tid1)
        self.assertNotIn("Chunk from old task 1", out_p.get_raw_text())

        # Worker from Request 2 sends token -> MUST BE DISPLAYED
        self.window._handle_worker_token("Chunk from task 2", mode, tid2)
        self.assertIn("Chunk from task 2", out_p.get_raw_text())

    def test_stop_generation_does_not_save_to_history(self):
        mode = "translate"
        out_p = self.window.output_panels[mode]

        initial_history_count = len(history_manager.get_records(mode=mode))

        self.window._start_generation("Text to stop", mode)
        tid = self.window._current_task_ids[mode]
        self.window._handle_worker_token("Partial translation", mode, tid)

        # User clicks stop
        self.window._on_stop(mode)
        self.assertEqual(out_p.lbl_status.text(), "已停止")
        self.assertIn("Partial translation", out_p.get_raw_text())

        # Worker emits stopped
        self.window._handle_worker_stopped("Partial translation", mode, tid)
        self.assertEqual(out_p.lbl_status.text(), "已停止")

        # History count must NOT increase
        final_history_count = len(history_manager.get_records(mode=mode))
        self.assertEqual(final_history_count, initial_history_count)

    def test_proxy_env_routing_respect_and_bypass(self):
        os.environ["HTTP_PROXY"] = "http://test-proxy:8080"
        os.environ["HTTPS_PROXY"] = "http://test-proxy:8080"
        try:
            # 1. Loopback addresses bypass proxy
            local_client = create_httpx_client("http://127.0.0.1:8001/v1")
            self.assertFalse(local_client._trust_env)
            local_client.close()

            # 2. Remote addresses respect proxy
            remote_client = create_httpx_client("https://api.deepseek.com/v1")
            self.assertTrue(remote_client._trust_env)
            remote_client.close()
        finally:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)

if __name__ == "__main__":
    unittest.main()

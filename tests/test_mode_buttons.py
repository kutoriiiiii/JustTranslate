# -*- coding: utf-8 -*-
"""Unit tests for mode-specific button texts and image OCR button state transitions."""

import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from ui.components.input_panel import InputPanel, MODE_BUTTON_TEXTS

app = QApplication.instance() or QApplication([])

class TestModeButtons(unittest.TestCase):
    """Verifies submit button labels match current mode and image preview lifecycle."""

    def test_initial_button_texts_per_mode(self):
        panel_tr = InputPanel(mode="translate")
        self.assertEqual(panel_tr.btn_submit.text(), "🚀 翻译")

        panel_pol = InputPanel(mode="polish")
        self.assertEqual(panel_pol.btn_submit.text(), "✨ 润色")

        panel_dict = InputPanel(mode="dictionary")
        self.assertEqual(panel_dict.btn_submit.text(), "🔎 查询")

    def test_dynamic_set_mode(self):
        panel = InputPanel(mode="translate")
        self.assertEqual(panel.btn_submit.text(), "🚀 翻译")

        panel.set_mode("polish")
        self.assertEqual(panel.btn_submit.text(), "✨ 润色")

        panel.set_mode("dictionary")
        self.assertEqual(panel.btn_submit.text(), "🔎 查询")

        panel.set_mode("translate")
        self.assertEqual(panel.btn_submit.text(), "🚀 翻译")

    def test_image_loaded_and_cleared_transitions(self):
        panel = InputPanel(mode="polish")
        self.assertEqual(panel.btn_submit.text(), "✨ 润色")

        # Simulate loading an image
        dummy_img = QImage(32, 32, QImage.Format_RGB32)
        panel.set_image_from_qimage(dummy_img)
        self.assertEqual(panel.btn_submit.text(), "🔍 识别并处理 (Ctrl+Enter)")

        # Clear image: must restore the polish mode text, NOT generic '执行处理'
        panel.clear_image()
        self.assertEqual(panel.btn_submit.text(), "✨ 润色")

        # Test dictionary mode image clear
        panel_dict = InputPanel(mode="dictionary")
        panel_dict.set_image_from_qimage(dummy_img)
        self.assertEqual(panel_dict.btn_submit.text(), "🔍 识别并处理 (Ctrl+Enter)")
        panel_dict.clear_image()
        self.assertEqual(panel_dict.btn_submit.text(), "🔎 查询")

if __name__ == "__main__":
    unittest.main()

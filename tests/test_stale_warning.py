# -*- coding: utf-8 -*-
"""Unit tests for stale output warning on source text edits."""

import unittest
from PySide6.QtWidgets import QApplication
from ui.components.input_panel import InputPanel
from ui.components.output_panel import OutputPanel
from ui.components.dictionary_card_panel import DictionaryCardPanel

app = QApplication.instance() or QApplication([])

class TestStaleWarning(unittest.TestCase):
    """Verifies that modifications to source text display the amber stale badge and programmatic changes do not."""

    def test_output_panel_stale_warning_badge(self):
        panel = OutputPanel(title="译文展示", mode="translate")
        self.assertTrue(panel.lbl_stale_warning.isHidden())
        self.assertEqual(panel.lbl_stale_warning.text(), "⚠ 原文已修改，结果可能不准确")

        panel.set_stale_warning(True)
        self.assertFalse(panel.lbl_stale_warning.isHidden())

        panel.set_stale_warning(False)
        self.assertTrue(panel.lbl_stale_warning.isHidden())

    def test_dictionary_card_panel_stale_warning_badge(self):
        panel = DictionaryCardPanel(title="词典释义")
        self.assertTrue(panel.lbl_stale_warning.isHidden())
        self.assertEqual(panel.lbl_stale_warning.text(), "⚠ 原文已修改，结果可能不准确")

        panel.set_stale_warning(True)
        self.assertFalse(panel.lbl_stale_warning.isHidden())

        panel.set_stale_warning(False)
        self.assertTrue(panel.lbl_stale_warning.isHidden())

    def test_user_edit_emits_signal_but_programmatic_does_not(self):
        panel = InputPanel()
        emitted_texts = []
        panel.user_text_changed.connect(lambda txt: emitted_texts.append(txt))

        # 1. Programmatic set_text should NOT emit user_text_changed
        panel.set_text("Programmatic content from history/OCR")
        self.assertEqual(len(emitted_texts), 0)

        # 2. User simulated edit via editor directly SHOULD emit user_text_changed
        panel.editor.insertPlainText(" user typed edit")
        self.assertGreater(len(emitted_texts), 0)
        self.assertIn("user typed edit", emitted_texts[-1])

    def test_stale_logic_simulation(self):
        in_p = InputPanel()
        out_p = OutputPanel()
        
        # Simulate request starting with snapshot
        snapshot = "Hello World"
        in_p.set_text(snapshot)
        out_p.set_stale_warning(False)
        self.assertTrue(out_p.lbl_stale_warning.isHidden())

        # User modifies text
        in_p.editor.setPlainText("Hello World Edited")
        if in_p.get_text() != snapshot:
            out_p.set_stale_warning(True)
        self.assertFalse(out_p.lbl_stale_warning.isHidden())

        # User changes back to exact snapshot
        in_p.editor.setPlainText("Hello World")
        if in_p.get_text() == snapshot:
            out_p.set_stale_warning(False)
        self.assertTrue(out_p.lbl_stale_warning.isHidden())

if __name__ == "__main__":
    unittest.main()

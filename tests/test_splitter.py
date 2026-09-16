# -*- coding: utf-8 -*-
"""Unit tests for BalancedSplitter anti-collapse mechanism and 1:1 double-click reset."""

import unittest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from ui.components.balanced_splitter import BalancedSplitter, BalancedSplitterHandle
from ui.components.input_panel import InputPanel
from ui.components.output_panel import OutputPanel

app = QApplication.instance() or QApplication([])


class TestBalancedSplitter(unittest.TestCase):
    def setUp(self):
        self.splitter = BalancedSplitter(Qt.Horizontal)
        self.w1 = QWidget()
        self.w2 = QWidget()
        self.w1.setMinimumWidth(280)
        self.w2.setMinimumWidth(280)
        self.splitter.addWidget(self.w1)
        self.splitter.addWidget(self.w2)
        self.splitter.resize(1000, 600)
        self.splitter.show()

    def tearDown(self):
        self.splitter.close()

    def test_anti_collapse_property(self):
        # Children collapsible must be disabled to prevent 0-width collapse
        self.assertFalse(self.splitter.childrenCollapsible())
        self.assertEqual(self.splitter.handleWidth(), 6)

    def test_handle_type_and_tooltip(self):
        handle = self.splitter.handle(1)
        self.assertIsInstance(handle, BalancedSplitterHandle)
        self.assertIn("1:1", handle.toolTip())
        self.assertEqual(handle.cursor().shape(), Qt.SplitHCursor)

    def test_extreme_left_drag_clamped(self):
        # Attempt to drag all the way to the left (10px)
        self.splitter.setSizes([10, 990])
        sizes = self.splitter.sizes()
        self.assertGreaterEqual(sizes[0], 280, "Left panel collapsed below minimum width!")
        self.assertGreater(sizes[1], 0)

    def test_extreme_right_drag_clamped(self):
        # Attempt to drag all the way to the right (10px)
        self.splitter.setSizes([990, 10])
        sizes = self.splitter.sizes()
        self.assertGreaterEqual(sizes[1], 280, "Right panel collapsed below minimum width!")
        self.assertGreater(sizes[0], 0)

    def test_double_click_resets_equal_balance(self):
        # First set asymmetric sizes
        self.splitter.setSizes([280, 714])
        self.assertNotEqual(self.splitter.sizes()[0], self.splitter.sizes()[1])

        # Double click handle
        handle = self.splitter.handle(1)
        dbl_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(2, 2),
            QPointF(2, 2),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        handle.mouseDoubleClickEvent(dbl_event)

        sizes = self.splitter.sizes()
        # Should be reset to equal 1:1 split (within 2px rounding)
        self.assertAlmostEqual(sizes[0], sizes[1], delta=2)

    def test_panel_components_have_minimum_width(self):
        input_panel = InputPanel(title="测试输入", placeholder="...")
        output_panel = OutputPanel(title="测试输出")
        self.assertGreaterEqual(input_panel.minimumWidth(), 280)
        self.assertGreaterEqual(output_panel.minimumWidth(), 280)


if __name__ == '__main__':
    unittest.main()

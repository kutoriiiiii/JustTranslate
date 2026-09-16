# -*- coding: utf-8 -*-
"""Custom QSplitter with anti-collapse protection and double-click 1:1 balance reset."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QSplitterHandle


class BalancedSplitterHandle(QSplitterHandle):
    """Splitter handle supporting double-click to reset equal 50/50 split."""

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter):
        super().__init__(orientation, parent)
        self.setToolTip("左右拖动调整两栏宽度 | 双击重置为 1:1 对等分栏")
        self.setCursor(Qt.SplitHCursor if orientation == Qt.Horizontal else Qt.SplitVCursor)

    def mouseDoubleClickEvent(self, event):
        """Resets adjacent splitter panels to equal 1:1 width on left-button double click."""
        if event.button() == Qt.LeftButton:
            splitter = self.splitter()
            if splitter:
                total_w = sum(splitter.sizes())
                if total_w > 0:
                    half = total_w // 2
                    splitter.setSizes([half, total_w - half])
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)


class BalancedSplitter(QSplitter):
    """
    QSplitter with anti-collapse protection and easy double-click reset.

    Ensures childrenCollapsible is permanently False and installs BalancedSplitterHandle.
    """

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(6)

    def createHandle(self) -> QSplitterHandle:
        return BalancedSplitterHandle(self.orientation(), self)

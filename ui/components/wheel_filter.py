# -*- coding: utf-8 -*-
"""Custom controls and event filters to unbind mouse wheel from dropdowns and spin boxes."""

from PySide6.QtWidgets import (
    QWidget, QComboBox, QSpinBox, QDoubleSpinBox, QScrollArea, QApplication
)
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import Qt, QEvent, QObject, QPointF


def forward_wheel_to_scroll(widget: QWidget, event: QWheelEvent):
    """Transparently forward wheel events from child controls to enclosing QScrollArea viewport."""
    parent = widget.parentWidget()
    scroll_area = None
    while parent:
        if isinstance(parent, QScrollArea):
            scroll_area = parent
            break
        parent = parent.parentWidget()

    if scroll_area:
        vp = scroll_area.viewport()
        vp_pos = vp.mapFromGlobal(widget.mapToGlobal(event.position().toPoint()))
        forwarded = QWheelEvent(
            QPointF(vp_pos),
            event.globalPosition(),
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted()
        )
        QApplication.sendEvent(vp, forwarded)
    else:
        event.ignore()


class NoWheelComboBox(QComboBox):
    """QComboBox that completely unbinds the mouse wheel, forwarding it to the enclosing page scroll area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent):
        forward_wheel_to_scroll(self, event)


class NoWheelSpinBox(QSpinBox):
    """QSpinBox that completely unbinds the mouse wheel, forwarding it to the enclosing page scroll area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent):
        forward_wheel_to_scroll(self, event)


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that completely unbinds the mouse wheel, forwarding it to the enclosing page scroll area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent):
        forward_wheel_to_scroll(self, event)


class GlobalNoWheelEventFilter(QObject):
    """Global event filter installed on QApplication to prevent any mouse wheel
    from accidentally modifying QComboBox, QSpinBox, or QDoubleSpinBox values,
    while smoothly forwarding wheel events to any enclosing QScrollArea."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            if isinstance(watched, (QComboBox, QSpinBox, QDoubleSpinBox)):
                if isinstance(watched, QComboBox):
                    popup = watched.view()
                    if popup and popup.isVisible():
                        return False
                forward_wheel_to_scroll(watched, event)
                return True

        return super().eventFilter(watched, event)


NoWheelEventFilter = GlobalNoWheelEventFilter
_forward_wheel_to_scroll = forward_wheel_to_scroll

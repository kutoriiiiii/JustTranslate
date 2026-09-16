# -*- coding: utf-8 -*-
"""Unit tests for the About tab in SettingsDialog."""

import unittest
from PySide6.QtWidgets import QApplication, QLabel, QComboBox, QScrollArea
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from ui.components.settings_dialog import SettingsDialog
from config.settings import APP_NAME, APP_VERSION, APP_AUTHOR, DEFAULT_PROFILES

app = QApplication.instance() or QApplication([])

class TestAboutTab(unittest.TestCase):
    def setUp(self):
        self.dialog = SettingsDialog()

    def tearDown(self):
        self.dialog.close()

    def test_about_tab_exists(self):
        tab_names = [self.dialog.tabs.tabText(i) for i in range(self.dialog.tabs.count())]
        self.assertIn("关于", tab_names)
        about_idx = tab_names.index("关于")
        about_widget = self.dialog.tabs.widget(about_idx)
        self.assertIsNotNone(about_widget)

    def test_about_tab_author_and_version(self):
        tab_names = [self.dialog.tabs.tabText(i) for i in range(self.dialog.tabs.count())]
        about_idx = tab_names.index("关于")
        about_widget = self.dialog.tabs.widget(about_idx)

        # Collect all label texts within the About tab
        labels = about_widget.findChildren(QLabel)
        label_texts = [lbl.text() for lbl in labels]

        # Verify author is Kutori
        self.assertIn(APP_AUTHOR, label_texts)
        self.assertEqual(APP_AUTHOR, "Kutori")

        # Verify version is 1.1.2
        self.assertIn(APP_VERSION, label_texts)
        self.assertEqual(APP_VERSION, "1.1.2")

        # Verify app name
        self.assertIn(APP_NAME, label_texts)
        self.assertEqual(APP_NAME, "Just Translate")

    def test_icon_path_resolution(self):
        icon_path = self.dialog._resolve_icon_path()
        self.assertTrue(icon_path.exists())
        self.assertTrue(str(icon_path).endswith("icon.png"))

    def test_default_deepseek_model_is_flash(self):
        ds_profile = next((p for p in DEFAULT_PROFILES if p.get("id") == "deepseek"), None)
        self.assertIsNotNone(ds_profile)
        self.assertEqual(ds_profile.get("model"), "deepseek-flash")

    def test_combobox_wheel_does_not_change_selection(self):
        combos = self.dialog.findChildren(QComboBox)
        self.assertGreater(len(combos), 0)

        for cb in combos:
            if cb.count() <= 1:
                continue
            cb.setCurrentIndex(0)
            initial_index = cb.currentIndex()
            initial_text = cb.currentText()

            # Simulate mouse wheel scroll down
            event_down = QWheelEvent(
                QPointF(10, 10),
                QPointF(10, 10),
                QPoint(0, 0),
                QPoint(0, -120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False
            )
            app.notify(cb, event_down)

            self.assertEqual(
                cb.currentIndex(),
                initial_index,
                f"ComboBox '{cb.objectName()}' changed selection on wheel scroll down!"
            )
            self.assertEqual(cb.currentText(), initial_text)

            # Simulate mouse wheel scroll up
            event_up = QWheelEvent(
                QPointF(10, 10),
                QPointF(10, 10),
                QPoint(0, 0),
                QPoint(0, 120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False
            )
            app.notify(cb, event_up)

            self.assertEqual(
                cb.currentIndex(),
                initial_index,
                f"ComboBox '{cb.objectName()}' changed selection on wheel scroll up!"
            )
            self.assertEqual(cb.currentText(), initial_text)

    def test_scroll_areas_exist_in_tabs(self):
        scroll_areas = self.dialog.findChildren(QScrollArea)
        self.assertGreaterEqual(len(scroll_areas), 4)

    def test_global_no_wheel_filter_intercepts_spin_and_combo(self):
        from ui.components.wheel_filter import GlobalNoWheelEventFilter, NoWheelComboBox, NoWheelSpinBox
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        
        filter_obj = GlobalNoWheelEventFilter()
        w = QWidget()
        layout = QVBoxLayout(w)
        cb = NoWheelComboBox()
        cb.addItems(["Alpha", "Beta", "Gamma"])
        sb = NoWheelSpinBox()
        sb.setRange(0, 100)
        sb.setValue(50)
        layout.addWidget(cb)
        layout.addWidget(sb)

        event = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False
        )
        self.assertTrue(filter_obj.eventFilter(cb, event))
        self.assertEqual(cb.currentIndex(), 0)
        self.assertTrue(filter_obj.eventFilter(sb, event))
        self.assertEqual(sb.value(), 50)


if __name__ == "__main__":
    unittest.main()

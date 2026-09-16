# -*- coding: utf-8 -*-
"""Unit tests for the About tab in SettingsDialog."""

import unittest
from PySide6.QtWidgets import QApplication, QLabel
from ui.components.settings_dialog import SettingsDialog
from config.settings import APP_NAME, APP_VERSION, APP_AUTHOR

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

        # Verify version is 1.0.1
        self.assertIn(APP_VERSION, label_texts)
        self.assertEqual(APP_VERSION, "1.0.1")

        # Verify app name
        self.assertIn(APP_NAME, label_texts)
        self.assertEqual(APP_NAME, "Just Translate")

    def test_icon_path_resolution(self):
        icon_path = self.dialog._resolve_icon_path()
        self.assertTrue(icon_path.exists())
        self.assertTrue(str(icon_path).endswith("icon.png"))

if __name__ == "__main__":
    unittest.main()

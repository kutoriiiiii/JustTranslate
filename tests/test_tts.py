# -*- coding: utf-8 -*-
"""Unit tests for Windows Native SAPI & Edge Neural TTS Manager."""

import unittest
from PySide6.QtWidgets import QApplication
from core.tts_manager import TTSManager, EDGE_VOICE_MAP
from config.settings import settings

# Ensure QApplication exists for QObject and QTimer
app = QApplication.instance() or QApplication([])

class TestTTSManager(unittest.TestCase):
    def setUp(self):
        self.tts = TTSManager.get_instance()

    def test_singleton_instance(self):
        self.assertIs(self.tts, TTSManager.get_instance())

    def test_sapi_availability(self):
        # On Windows, SAPI should be available
        avail = self.tts.is_sapi_available()
        self.assertIsInstance(avail, bool)

    def test_edge_voice_mapping(self):
        # Ensure major languages have corresponding Edge neural voices mapped
        major_langs = ["Chinese", "English", "Japanese", "French", "German", "Spanish", "Russian", "Korean"]
        for lang in major_langs:
            self.assertIn(lang, EDGE_VOICE_MAP)
            self.assertTrue(EDGE_VOICE_MAP[lang].endswith("Neural"))

    def test_local_voice_detection(self):
        # Auto or empty should always return True (no notice needed)
        self.assertTrue(self.tts.has_local_voice_for_language("Auto"))
        self.assertTrue(self.tts.has_local_voice_for_language(""))

        # Do not depend on the voice packs installed on the machine running tests.
        original_languages = self.tts._local_languages.copy()
        try:
            self.tts._local_languages = {"Chinese", "English"}
            self.assertTrue(self.tts.has_local_voice_for_language("Chinese"))
            self.assertTrue(self.tts.has_local_voice_for_language("English"))
            self.assertFalse(self.tts.has_local_voice_for_language("Japanese"))
            self.assertFalse(self.tts.has_local_voice_for_language("French"))
        finally:
            self.tts._local_languages = original_languages

    def test_detect_language(self):
        self.assertEqual(self.tts.detect_language("こんにちは世界"), "Japanese")
        self.assertEqual(self.tts.detect_language("안녕하세요"), "Korean")
        self.assertEqual(self.tts.detect_language("Привет мир"), "Russian")
        self.assertEqual(self.tts.detect_language("مرحبا بالعالم"), "Arabic")
        self.assertEqual(self.tts.detect_language("สวัสดีชาวโลก"), "Thai")
        self.assertEqual(self.tts.detect_language("你好，世界！"), "Chinese")
        self.assertEqual(self.tts.detect_language("Hello world, how are you?"), "English")

    def test_stop_when_not_speaking(self):
        self.tts.stop()
        self.assertFalse(self.tts.is_speaking())

    def test_empty_speak_ignored(self):
        self.tts.speak("")
        self.assertFalse(self.tts.is_speaking())
        self.tts.speak("   ")
        self.assertFalse(self.tts.is_speaking())

    def test_tts_dialog_settings_default(self):
        # Default should be False unless user checked "never show again"
        suppressed = settings.get("tts_suppress_missing_voice_dialog", None)
        self.assertIsNotNone(suppressed)
        self.assertIsInstance(suppressed, bool)


if __name__ == '__main__':
    unittest.main()



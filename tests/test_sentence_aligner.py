# -*- coding: utf-8 -*-
"""Unit tests for sentence segmentation, cross-text sentence alignment, and OCR capability detection."""

import unittest
from core.sentence_aligner import (
    split_sentences_with_spans,
    find_sentence_at_position,
    map_sentence_index,
    SentenceSpan
)
from core.ocr_client import is_vision_model, check_ocr_capability

class TestSentenceAlignerAndOCR(unittest.TestCase):

    def test_cjk_sentence_splitting(self):
        text = "你好世界！这是第一句。你想听第二句吗？当然；这很棒……“这是引用的句子！”"
        spans = split_sentences_with_spans(text)
        self.assertEqual(len(spans), 6)
        self.assertEqual(spans[0].text, "你好世界！")
        self.assertEqual(spans[1].text, "这是第一句。")
        self.assertEqual(spans[2].text, "你想听第二句吗？")
        self.assertEqual(spans[3].text, "当然；")
        self.assertEqual(spans[4].text, "这很棒……")
        self.assertEqual(spans[5].text, "“这是引用的句子！”")

    def test_latin_sentence_splitting_with_abbreviations_and_numbers(self):
        text = "Hello world! This costs $3.14 approx. Please visit dr. Smith at 5 p.m."
        # Notice 3.14 should not split.
        spans = split_sentences_with_spans(text)
        self.assertTrue(len(spans) >= 2)
        self.assertEqual(spans[0].text, "Hello world!")

    def test_numbered_markdown_lists(self):
        text = (
            "1: Add shortcut keys for quick access to synonyms.\n"
            "2: Wrap the output section in a box.\n"
            "3: The copy button should only copy main text."
        )
        spans = split_sentences_with_spans(text)
        self.assertEqual(len(spans), 3)
        self.assertEqual(spans[0].index, 0)
        self.assertTrue("1: Add shortcut keys" in spans[0].text)
        self.assertEqual(spans[1].index, 1)
        self.assertTrue("2: Wrap the output" in spans[1].text)
        self.assertEqual(spans[2].index, 2)
        self.assertTrue("3: The copy button" in spans[2].text)

    def test_find_sentence_at_position(self):
        text = "First sentence. Second sentence. Third sentence."
        spans = split_sentences_with_spans(text)
        # Position inside first sentence
        s0 = find_sentence_at_position(spans, 5)
        self.assertIsNotNone(s0)
        self.assertEqual(s0.index, 0)
        self.assertEqual(s0.text, "First sentence.")

        # Position inside second sentence
        pos_second = text.find("Second") + 2
        s1 = find_sentence_at_position(spans, pos_second)
        self.assertIsNotNone(s1)
        self.assertEqual(s1.index, 1)
        self.assertEqual(s1.text, "Second sentence.")

    def test_sentence_index_mapping(self):
        # 1-to-1 exact mapping
        self.assertEqual(map_sentence_index(0, 5, 5), 0)
        self.assertEqual(map_sentence_index(2, 5, 5), 2)
        self.assertEqual(map_sentence_index(4, 5, 5), 4)

        # 3 sentences mapping to 6 sentences
        self.assertEqual(map_sentence_index(0, 3, 6), 0)
        self.assertIn(map_sentence_index(1, 3, 6), (2, 3))
        self.assertEqual(map_sentence_index(2, 3, 6), 5)

        # 6 sentences mapping to 3 sentences
        self.assertEqual(map_sentence_index(0, 6, 3), 0)
        self.assertEqual(map_sentence_index(5, 6, 3), 2)

        # Single sentence edge cases
        self.assertEqual(map_sentence_index(0, 1, 5), 0)
        self.assertEqual(map_sentence_index(0, 5, 1), 0)
        self.assertEqual(map_sentence_index(0, 0, 0), 0)

    def test_is_vision_model(self):
        self.assertTrue(is_vision_model("gpt-4o"))
        self.assertTrue(is_vision_model("gpt-4o-mini"))
        self.assertTrue(is_vision_model("qwen2.5-vl-7b-instruct"))
        self.assertTrue(is_vision_model("GLM-4V"))
        self.assertTrue(is_vision_model("GLM-OCR"))
        self.assertTrue(is_vision_model("llava-v1.6-vicuna-7b"))
        self.assertTrue(is_vision_model("gemini-1.5-flash"))
        self.assertTrue(is_vision_model("claude-3-5-sonnet"))

        self.assertFalse(is_vision_model("deepseek-chat"))
        self.assertFalse(is_vision_model("deepseek-reasoner"))
        self.assertFalse(is_vision_model("qwen2.5-7b"))
        self.assertFalse(is_vision_model("qwen2.5:7b"))
        self.assertFalse(is_vision_model("Hy-MT2-7B"))
        self.assertFalse(is_vision_model("llama-3.1-8b-instruct"))

    def test_check_ocr_capability(self):
        # Profile with dedicated OCR model
        p_ocr = {"id": "custom", "model": "deepseek-chat", "ocr_model": "GLM-OCR", "base_url": "http://127.0.0.1:8001/v1", "api_key": "123"}
        has_ocr, msg, url, key, m = check_ocr_capability(p_ocr)
        self.assertTrue(has_ocr)
        self.assertEqual(m, "GLM-OCR")

        # Profile whose main model is vision
        p_vision = {"id": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1", "api_key": "sk-123"}
        has_ocr, msg, url, key, m = check_ocr_capability(p_vision)
        self.assertTrue(has_ocr)
        self.assertEqual(m, "gpt-4o-mini")

        # Pure text profile without OCR model
        p_text = {"id": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1", "api_key": "sk-123"}
        has_ocr, msg, url, key, m = check_ocr_capability(p_text)
        self.assertFalse(has_ocr)
        self.assertIn("纯文本模型", msg)

if __name__ == "__main__":
    unittest.main()

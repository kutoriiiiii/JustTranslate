"""Unit tests for LingoDesk core logic."""

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.lang_detector import detect_language, suggest_target_language
from config.default_prompts import build_prompt_messages, DEFAULT_PROMPTS
from config.settings import AppSettings
from core.llm_client import LLMClient

class TestCoreLogic(unittest.TestCase):

    def test_language_detection(self):
        self.assertEqual(detect_language("Hello world, how are you?"), "English")
        self.assertEqual(detect_language("你好，世界！"), "Chinese")
        self.assertEqual(detect_language("こんにちは、元気ですか？"), "Japanese")
        self.assertEqual(detect_language("ラーメンが美味しい"), "Japanese")

        # 复杂混合场景：英文中嵌入中文引用（如用户反馈场景）
        mixed_en = (
            "Languages should be displayed by their Chinese names, such as 中文/英文/日语. "
            "Add a text prompt to the copy button: 已复制到剪贴板."
        )
        self.assertEqual(detect_language(mixed_en), "English")

        # 中文中混入英文缩写 (API, UI, Markdown)
        mixed_zh = "请检查这个 API 和 UI 的运行状态，导出 Markdown 格式与配置。"
        self.assertEqual(detect_language(mixed_zh), "Chinese")

    def test_suggest_target_language(self):
        self.assertEqual(suggest_target_language("Chinese"), "English")
        self.assertEqual(suggest_target_language("English"), "Chinese")
        self.assertEqual(suggest_target_language("Japanese"), "Chinese")

    def test_prompt_builder(self):
        # 翻译模式
        msgs = build_prompt_messages("translate", "English", "Chinese", "Good morning")
        self.assertEqual(len(msgs), 2)
        self.assertIn("翻译", msgs[0]["content"])
        self.assertIn("Good morning", msgs[1]["content"])

        # 润色模式：验证英文同语言润色且严禁翻译约束
        msgs_polish = build_prompt_messages("polish", "English", "English", "I is happy.")
        self.assertIn("STRICT SAME-LANGUAGE POLISHING", msgs_polish[0]["content"])
        self.assertIn("NEVER translate into Chinese", msgs_polish[0]["content"])
        self.assertIn("I is happy.", msgs_polish[1]["content"])

        # 润色模式：验证中文同语言润色约束
        msgs_polish_zh = build_prompt_messages("polish", "Chinese", "Chinese", "这是一句测试。")
        self.assertIn("严格同语言润色", msgs_polish_zh[0]["content"])
        self.assertIn("严禁翻译", msgs_polish_zh[0]["content"])
        self.assertIn("这是一句测试。", msgs_polish_zh[1]["content"])

        # 词典模式：中日词典严格限定日文与中文，严禁出现英文
        msgs_dict_jp = build_prompt_messages("dictionary", "Chinese", "Japanese", "吃饭")
        self.assertIn("日文", msgs_dict_jp[0]["content"])
        self.assertIn("中文", msgs_dict_jp[0]["content"])
        self.assertIn("严禁出现任何英文", msgs_dict_jp[0]["content"])
        self.assertIn("日文", msgs_dict_jp[1]["content"])
        self.assertIn("严禁出现任何英文", msgs_dict_jp[1]["content"])

        # 词典模式：英中词典严格限定英文与中文
        msgs_dict_en = build_prompt_messages("dictionary", "English", "Chinese", "ephemeral")
        self.assertIn("英文", msgs_dict_en[0]["content"])
        self.assertIn("中文", msgs_dict_en[0]["content"])
        self.assertIn("词典", msgs_dict_en[0]["content"])

    def test_extract_polished_body(self):
        from core.text_utils import extract_polished_body

        # 样式 1: 带分割线与【优化要点】
        raw_1 = (
            "这是一段优化后的商务正文，更加地道流畅。\n\n"
            "---\n"
            "【优化要点】\n"
            "- 调整了修辞搭配\n"
            "- 修正了语序"
        )
        self.assertEqual(extract_polished_body(raw_1), "这是一段优化后的商务正文，更加地道流畅。")

        # 样式 2: 带有 ### 优化要点
        raw_2 = (
            "I am pleased to announce the new release.\n\n"
            "### 优化要点\n"
            "1. Simplified word choices"
        )
        self.assertEqual(extract_polished_body(raw_2), "I am pleased to announce the new release.")

        # 样式 3: 带有开头的“润色结果：”前缀
        raw_3 = (
            "### 润色正文：\n"
            "这是纯净的润色内容。\n\n"
            "【修改说明】\n"
            "- 纠正标点符号"
        )
        self.assertEqual(extract_polished_body(raw_3), "这是纯净的润色内容。")

        # 样式 4: 仅有正文，无优化要点
        raw_4 = "Simply a pure polished sentence."
        self.assertEqual(extract_polished_body(raw_4), "Simply a pure polished sentence.")

    def test_llm_client_timeout_and_config(self):
        client = LLMClient(base_url="http://127.0.0.1:8080", timeout=30.0)
        self.assertEqual(client.timeout, 30.0)
        self.assertEqual(client._get_endpoint(), "http://127.0.0.1:8080/v1/chat/completions")

        client2 = LLMClient(base_url="http://127.0.0.1:8080/v1", timeout=30.0)
        self.assertEqual(client2._get_endpoint(), "http://127.0.0.1:8080/v1/chat/completions")

        # 火山引擎等带 /v3 版本号的端点
        client3 = LLMClient(base_url="https://ark.cn-beijing.volces.com/api/coding/v3")
        self.assertEqual(client3._get_endpoint(), "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions")

        # 直接指定 /chat/completions 的端点
        client4 = LLMClient(base_url="https://api.example.com/custom/chat/completions")
        self.assertEqual(client4._get_endpoint(), "https://api.example.com/custom/chat/completions")

    def test_settings_persistence(self):
        test_file = PROJECT_ROOT / "tests" / "temp_settings.json"
        if test_file.exists():
            test_file.unlink()

        st = AppSettings(test_file)
        self.assertEqual(st.get("active_profile_id"), "llama_cpp")

        st.set("temperature", 0.7)
        self.assertEqual(st.get("temperature"), 0.7)

        # 再次读取验证持久化
        st2 = AppSettings(test_file)
        self.assertEqual(st2.get("temperature"), 0.7)

        # 测试新增的最近其他语言记忆功能
        recents = st.get_recent_other_langs(is_src=False)
        self.assertEqual(len(recents), 2)
        st.add_recent_other_lang(is_src=False, lang_code="German")
        st.add_recent_other_lang(is_src=False, lang_code="Spanish")
        recents2 = st.get_recent_other_langs(is_src=False)
        self.assertEqual(recents2, ["Spanish", "German"])

        if test_file.exists():
            test_file.unlink()

    def test_language_registry(self):
        from config.languages import COMMON_LANGUAGES, EXTRA_LANGUAGES, get_language_label
        self.assertEqual(len(COMMON_LANGUAGES), 3)
        self.assertGreaterEqual(len(EXTRA_LANGUAGES), 10)
        self.assertIn("Korean", [c for _, c in EXTRA_LANGUAGES])
        self.assertIn("French", [c for _, c in EXTRA_LANGUAGES])
        self.assertIn("German", [c for _, c in EXTRA_LANGUAGES])

if __name__ == "__main__":
    unittest.main()

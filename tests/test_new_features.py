# -*- coding: utf-8 -*-
"""Unit tests for Eco Mode, Model Discovery / Extraction, and Synonyms & Antonyms dictionary mode."""

import unittest
from config.default_prompts import build_prompt_messages, DEFAULT_PROMPTS
from core.llm_client import LLMClient
from config.settings import DEFAULT_SETTINGS

class TestNewFeatures(unittest.TestCase):

    def test_settings_eco_mode_default(self):
        self.assertIn("eco_mode", DEFAULT_SETTINGS)
        self.assertFalse(DEFAULT_SETTINGS["eco_mode"])

    def test_eco_mode_prompts(self):
        # 1. 翻译模式对比
        normal_msgs = build_prompt_messages("translate", "English", "Chinese", "Hello world", eco_mode=False)
        eco_msgs = build_prompt_messages("translate", "English", "Chinese", "Hello world", eco_mode=True)
        
        normal_sys_len = len(normal_msgs[0]["content"])
        eco_sys_len = len(eco_msgs[0]["content"])
        self.assertLess(eco_sys_len, normal_sys_len * 0.4, "Eco system prompt must be significantly shorter")
        self.assertIn("[English->Chinese]", eco_msgs[1]["content"])

        # 2. 润色模式对比
        normal_polish = build_prompt_messages("polish", "English", "English", "This is an essay", eco_mode=False)
        eco_polish = build_prompt_messages("polish", "English", "English", "This is an essay", eco_mode=True)
        self.assertLess(len(eco_polish[0]["content"]), len(normal_polish[0]["content"]) * 0.4)
        self.assertIn("[Polish English Text", eco_polish[1]["content"])

        # 3. 纯文本格式在省钱模式下的极简指令
        eco_plain = build_prompt_messages("translate", "English", "Chinese", "Hello", output_format="plain", eco_mode=True)
        self.assertIn("纯文本", eco_plain[0]["content"])

    def test_synonyms_and_antonyms_dictionary_prompt(self):
        # 常规模式下的同反义词约束
        msgs = build_prompt_messages("dictionary", "English", "Chinese", "ephemeral", dict_type="syn_ant", eco_mode=False)
        sys_prompt = msgs[0]["content"]
        user_prompt = msgs[1]["content"]

        self.assertIn("同义词", sys_prompt)
        self.assertIn("反义词", sys_prompt)
        self.assertIn("严禁输出任何音标/拼音、例句、语法解析", sys_prompt)
        self.assertIn("同义词与反义词", user_prompt)

        # 省钱模式下的同反义词约束
        eco_msgs = build_prompt_messages("dictionary", "English", "Chinese", "ephemeral", dict_type="syn_ant", eco_mode=True)
        self.assertIn("同反义词词典", eco_msgs[0]["content"])
        self.assertIn("ephemeral", eco_msgs[1]["content"])
        self.assertIn("同义词", eco_msgs[1]["content"])

    def test_extract_models_from_json(self):
        # 1. Standard OpenAI response
        openai_data = {
            "object": "list",
            "data": [
                {"id": "gpt-4o", "object": "model"},
                {"id": "gpt-4o-mini", "object": "model"},
                {"id": "text-embedding-3-small", "object": "model"}
            ]
        }
        res1 = LLMClient._extract_models_from_json(openai_data)
        self.assertEqual(res1, ["gpt-4o", "gpt-4o-mini", "text-embedding-3-small"])

        # 2. Ollama / vLLM response
        ollama_data = {
            "models": [
                {"name": "qwen2.5:7b", "model": "qwen2.5:7b"},
                {"name": "llama3.1:8b", "model": "llama3.1:8b"}
            ]
        }
        res2 = LLMClient._extract_models_from_json(ollama_data)
        self.assertEqual(res2, ["llama3.1:8b", "qwen2.5:7b"])

        # 3. List of strings
        list_str_data = {
            "data": ["deepseek-chat", "deepseek-coder", "deepseek-chat"]
        }
        res3 = LLMClient._extract_models_from_json(list_str_data)
        self.assertEqual(res3, ["deepseek-chat", "deepseek-coder"])

        # 4. Bare list of dicts
        bare_list = [
            {"id": "model-z"},
            {"id": "model-a"}
        ]
        res4 = LLMClient._extract_models_from_json(bare_list)
        self.assertEqual(res4, ["model-a", "model-z"])

        # 5. Invalid / empty data
        res5 = LLMClient._extract_models_from_json(None)
        self.assertEqual(res5, [])
        res6 = LLMClient._extract_models_from_json({})
        self.assertEqual(res6, [])

    def test_output_panel_prepare_markdown(self):
        from ui.components.output_panel import OutputPanel
        raw = "joy\n[English]: pleasure\nhappiness"
        processed = OutputPanel._prepare_markdown(raw)
        self.assertIn("joy  \n", processed)
        self.assertIn("[English]: pleasure  \n", processed)

if __name__ == "__main__":
    unittest.main()

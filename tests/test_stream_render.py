# -*- coding: utf-8 -*-
"""Unit tests for smart Markdown detection and anti-flicker streaming finish."""

import unittest
from PySide6.QtWidgets import QApplication
from core.text_utils import has_markdown_features
from ui.components.output_panel import OutputPanel

app = QApplication.instance() or QApplication([])


class TestStreamRender(unittest.TestCase):
    def test_has_markdown_features_false_for_plain_text(self):
        plain_cases = [
            "人工智能正在深刻改变着各行各业的生产力方式。从自然语言处理到自动驾驶，技术的突破为我们提供了无限可能。",
            "Hello world! This is a simple translation of a paragraph.\nIt has multiple lines and punctuation.",
            "Today's date is 2026-09-15. The price is $12.50, and 100% of tasks completed.",
            "简单的第一句。紧接着是第二句，没有特殊的标记语法。"
        ]
        for text in plain_cases:
            self.assertFalse(has_markdown_features(text), f"Falsely detected Markdown in: {text}")

    def test_has_markdown_features_true_for_rich_markdown(self):
        rich_cases = [
            "# 一级标题\n正文内容",
            "### 详细分析",
            "代码示例如下：\n```python\nprint('hello')\n```",
            "| 列 1 | 列 2 |\n| --- | --- |\n| 数据 A | 数据 B |",
            "> 这是一个引言或重要说明",
            "- 第一项\n- 第二项\n- 第三项",
            "* 列表项 A\n* 列表项 B",
            "1. 步骤一\n2. 步骤二",
            "---\n分隔线下方",
            "包含 **粗体强调** 的段落",
            "参考链接：[官网](https://example.com)"
        ]
        for text in rich_cases:
            self.assertTrue(has_markdown_features(text), f"Failed to detect Markdown in: {text}")

    def test_output_panel_finish_streaming_plain_text_no_re_render(self):
        panel = OutputPanel(title="测试输出")
        panel.start_streaming()
        
        sample = "人工智能技术为跨语言沟通带来了前所未有的便利。"
        panel.append_chunk(sample)
        
        # Verify text before finish
        self.assertEqual(panel.browser.toPlainText().strip(), sample)
        
        # Call finish_streaming
        panel.finish_streaming()
        
        # In Plan B: plain text remains pure plain text without DOM wipe
        self.assertEqual(panel.browser.toPlainText().strip(), sample)
        # Verify HTML body doesn't wrap with table or header tags
        html = panel.browser.toHtml()
        self.assertNotIn("<table", html)
        self.assertNotIn("<h1", html)

    def test_output_panel_finish_streaming_markdown_renders_html(self):
        panel = OutputPanel(title="测试输出")
        panel.start_streaming()
        
        markdown_sample = "| 词汇 | 释义 |\n| --- | --- |\n| apple | 苹果 |"
        panel.append_chunk(markdown_sample)
        panel.finish_streaming()
        
        html = panel.browser.toHtml()
        self.assertIn("<table", html)

    def test_output_panel_polish_mode_finish_streaming_no_re_render(self):
        # 验证润色模式下，即使输出包含 --- 分割线与 【优化要点】 - 列表，流式结束后也绝对不执行 setHtml 重渲染
        panel = OutputPanel(title="润色结果与优化要点", mode="polish")
        panel.start_streaming()
        
        polish_sample = (
            "这是润色后的正文内容，表达更加自然、用词更加精准。\n\n"
            "---\n"
            "【优化要点】\n"
            "- 改善了句式衔接\n"
            "- 纠正了语病和用词"
        )
        panel.append_chunk(polish_sample)
        panel.finish_streaming()
        
        # 1. 验证流式打字结束后内容保持为纯文本排版，零重绘、零刷新
        self.assertEqual(panel.browser.toPlainText().strip(), polish_sample.strip())
        html = panel.browser.toHtml()
        self.assertNotIn("<hr", html)
        self.assertNotIn("<ul", html)
        self.assertNotIn("<li", html)

        # 2. 验证用户主动通过下拉框切换为 Markdown 格式时，正常支持富文本渲染
        panel._apply_current_format(is_stream_finish=False)
        html_manual = panel.browser.toHtml()
        self.assertTrue("<hr" in html_manual or "<ul" in html_manual or "<li" in html_manual)


if __name__ == '__main__':
    unittest.main()

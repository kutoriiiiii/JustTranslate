# -*- coding: utf-8 -*-
"""Unit tests for new features: HistoryManager, output formatting prompts, and MRU/settings."""

import unittest
import tempfile
from pathlib import Path
from core.history_manager import HistoryManager
from config.default_prompts import build_prompt_messages
from config.settings import AppSettings

class TestFeatures(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_history.db"
        self.settings_file = Path(self.temp_dir.name) / "test_settings.json"
        self.settings = AppSettings(self.settings_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_history_manager_crud_and_prune(self):
        hm = HistoryManager(self.db_path)
        self.assertEqual(hm.get_count(), 0)

        # 插入测试记录
        r1 = hm.add_record(
            mode="translate",
            source_lang="English",
            target_lang="Chinese",
            model="Hy-MT2-7B",
            input_text="Hello world",
            output_text="你好，世界",
            ttft_ms=120.5,
            speed_tok_s=35.0,
            duration_s=0.8
        )
        self.assertGreater(r1, 0)
        self.assertEqual(hm.get_count(), 1)

        # 查询与过滤
        records = hm.get_records(mode="translate")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["input_text"], "Hello world")
        self.assertEqual(records[0]["output_text"], "你好，世界")
        self.assertEqual(records[0]["model"], "Hy-MT2-7B")

        # 关键词模糊搜索
        kw_res = hm.get_records(keyword="世界")
        self.assertEqual(len(kw_res), 1)
        kw_empty = hm.get_records(keyword="不存在的内容")
        self.assertEqual(len(kw_empty), 0)

        # 测试容量自动修剪：设置全局 limit 为 3 条
        from config.settings import settings as global_settings
        old_limit = global_settings.get("history_limit", 100)
        try:
            global_settings.set("history_limit", 3)
            for i in range(5):
                hm.add_record(
                    mode="translate",
                    source_lang="English",
                    target_lang="Chinese",
                    model="test-model",
                    input_text=f"Sentence {i}",
                    output_text=f"句子 {i}"
                )
            self.assertEqual(hm.get_count(), 3)
        finally:
            global_settings.set("history_limit", old_limit)

        # 全部清空
        hm.clear_all()
        self.assertEqual(hm.get_count(), 0)

    def test_prompt_format_option(self):
        # 默认 Markdown
        msgs_md = build_prompt_messages(
            mode="translate",
            src_lang="English",
            target_lang="Chinese",
            text="Hello world",
            output_format="markdown"
        )
        self.assertNotIn("【排版格式硬性要求】", msgs_md[0]["content"])

        # 纯文本模式
        msgs_plain = build_prompt_messages(
            mode="translate",
            src_lang="English",
            target_lang="Chinese",
            text="Hello world",
            output_format="plain"
        )
        self.assertIn("【排版格式硬性要求】", msgs_plain[0]["content"])
        self.assertIn("纯文本", msgs_plain[0]["content"])
        self.assertIn("严禁使用任何 Markdown 格式标记", msgs_plain[0]["content"])

    def test_one_click_polish_prompt_language(self):
        # 验证润色英文译文时，系统指令与用户提示词均采用原生英文，杜绝中文干扰
        english_text = "This is a polished and refined translation."
        msgs = build_prompt_messages(
            mode="polish",
            src_lang="English",
            target_lang="English",
            text=english_text
        )
        self.assertIn("English", msgs[0]["content"])
        self.assertIn("STRICT SAME-LANGUAGE POLISHING", msgs[0]["content"])
        self.assertIn("NEVER translate into Chinese", msgs[0]["content"])
        self.assertIn("English", msgs[1]["content"])
        self.assertNotIn("请对以下", msgs[1]["content"])

        # 验证润色中文文本时，系统指令与用户提示词为母语级中文，杜绝外语翻译
        chinese_text = "这是一段需要润色的中文技术文档。"
        zh_msgs = build_prompt_messages(
            mode="polish",
            src_lang="Chinese",
            target_lang="Chinese",
            text=chinese_text
        )
        self.assertIn("中文", zh_msgs[0]["content"])
        self.assertIn("严格同语言润色", zh_msgs[0]["content"])
        self.assertIn("严禁翻译", zh_msgs[0]["content"])
        self.assertIn("中文", zh_msgs[1]["content"])

    def test_strip_unwanted_prefixes_and_copy(self):
        from core.text_utils import strip_unwanted_prefixes, extract_polished_body
        raw_output = (
            "重要提醒：请保持使用同种语言【English】进行润色输出，绝对不要翻译成其他语言：\n\n"
            "This is the polished sentence.\n\n"
            "---\n"
            "【优化要点】\n"
            "1. Enhanced vocabulary."
        )
        # 1. 验证展示文本自动剥离指令前缀
        cleaned = strip_unwanted_prefixes(raw_output)
        self.assertNotIn("重要提醒", cleaned)
        self.assertTrue(cleaned.startswith("This is the polished sentence."))

        # 2. 验证复制正文功能绝不继承指令前缀，且剔除优化要点
        body = extract_polished_body(raw_output)
        self.assertEqual(body, "This is the polished sentence.")

    def test_mode_synchronization_on_startup_and_switching(self):
        from PySide6.QtWidgets import QApplication
        from config.settings import settings as global_settings
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])

        # 测试 1: 当 last_mode 为 polish 时，启动后 control_bar 和 stacked widget 必须 100% 同步为 polish
        global_settings.set("last_mode", "polish")
        win_polish = MainWindow()
        try:
            self.assertEqual(win_polish.control_bar.get_current_mode(), "polish")
            self.assertTrue(win_polish.control_bar.btn_polish.isChecked())
            self.assertFalse(win_polish.control_bar.btn_translate.isChecked())
            self.assertEqual(win_polish.input_stack.currentIndex(), 1)
            self.assertEqual(win_polish.output_stack.currentIndex(), 1)
            self.assertFalse(win_polish.control_bar.btn_swap.isEnabled())
            self.assertFalse(win_polish.control_bar.btn_target_lang.isEnabled())
        finally:
            win_polish.close()

        # 测试 2: 当 last_mode 为 translate 时，启动后必须 100% 同步为 translate
        global_settings.set("last_mode", "translate")
        win_trans = MainWindow()
        try:
            self.assertEqual(win_trans.control_bar.get_current_mode(), "translate")
            self.assertTrue(win_trans.control_bar.btn_translate.isChecked())
            self.assertFalse(win_trans.control_bar.btn_polish.isChecked())
            self.assertEqual(win_trans.input_stack.currentIndex(), 0)
            self.assertEqual(win_trans.output_stack.currentIndex(), 0)
            self.assertTrue(win_trans.control_bar.btn_swap.isEnabled())
            self.assertTrue(win_trans.control_bar.btn_target_lang.isEnabled())

            # 动态切换模式并验证双向同步
            win_trans.control_bar.set_mode("dictionary", emit_signal=True)
            self.assertEqual(win_trans.control_bar.get_current_mode(), "dictionary")
            self.assertTrue(win_trans.control_bar.btn_dictionary.isChecked())
            self.assertEqual(win_trans.input_stack.currentIndex(), 2)
            self.assertEqual(win_trans.output_stack.currentIndex(), 2)
            self.assertEqual(global_settings.get("last_mode"), "dictionary")
        finally:
            win_trans.close()

    def test_render_markdown_tables_with_br_and_complex_markup(self):
        from core.text_utils import render_markdown_to_html
        from PySide6.QtWidgets import QTextBrowser, QApplication

        app = QApplication.instance() or QApplication([])

        table_md = (
            "| 项目 | 内容 |\n"
            "|------|------|\n"
            "| **词头与音标/假名** | 中文拼音: huàzhuàng; 英语国际音标: /hʊɑʒʊɑŋ/; 日语平假名: けしょう; 罗马音: keshō |\n"
            "| **词性与释义** | **动词**: 在面部或身体涂抹化妆品，以改变外观、修饰容貌。<br>**名词**: 通过化妆改变后的容貌状态；化妆用的化妆品。|\n"
            "| **典型例句** | 1. 她每天晚上都会化妆去上班。<br> -> Tā měi tiān wǎnshang dōu huàzhuāng qù gōngzuò.<br>2. 这款粉底液非常适合亚洲人的肤色。<br> -> Zhè kuǎn fěndǐyè fēicháng shìhé zhōuyà rén de sèpí.<br>3. 演员上台前需要仔细化妆。<br> -> Yǎnyuán shàng tái qián xūyào zǐxì huàzhuāng。 |\n"
            "| **常见搭配与近反义词** | **常见搭配**: <br>• 化妆打扮 (huàzhuāng dǎbàn) ：通过化妆修饰外貌<br>• 化妆品 (huàzhuāngpǐn) ：用于化妆的各类产品<br>• 化淡妆 (huà dànzhuāng) ：化妆淡<br>• 化浓妆 (huànóngzhuāng) ：化妆浓<br>• 化妆师 (huàzhuāngshī) ：专业化妆师<br><br>**近义词**: <br>• 修饰容貌 (xiūshì méiróng) ：通过手段改善容貌<br>• 涂抹化妆品 (túmò huàzhuāngpǐn) ：与“化妆”动作相近<br><br>**反义词**: <br>• 不化妆 (bù huàzhuāng) ：不涂抹化妆品<br>• 保持素颜 (bǎochí sùyán) ：保持自然未化妆的状态 |"
        )

        html = render_markdown_to_html(table_md)
        self.assertIn("<table", html)
        self.assertIn("<th>项目</th>", html)
        self.assertIn("<th>内容</th>", html)
        self.assertIn("动词", html)
        self.assertIn("典型例句", html)
        self.assertIn("常见搭配与近反义词", html)

        tb = QTextBrowser()
        tb.setHtml(html)
        plain = tb.toPlainText()
        # 确保所有 4 行表格内容均完整渲染，未发生截断丢损
        self.assertIn("词头与音标/假名", plain)
        self.assertIn("词性与释义", plain)
        self.assertIn("典型例句", plain)
        self.assertIn("常见搭配与近反义词", plain)
        self.assertIn("保持自然未化妆的状态", plain)
        self.assertGreater(len(plain), 500)

    def test_theme_manager_and_switching(self):
        from core.theme_manager import ThemeManager
        from ui.styles.modern_theme import get_theme_qss, DARK_THEME_QSS, LIGHT_THEME_QSS
        from config.settings import settings as global_settings

        tm = ThemeManager.get_instance()
        self.assertIsNotNone(tm)

        # 验证 QSS 样式表获取
        self.assertEqual(get_theme_qss(True), DARK_THEME_QSS)
        self.assertEqual(get_theme_qss(False), LIGHT_THEME_QSS)
        self.assertIn("#18181B", DARK_THEME_QSS)
        self.assertIn("#F8FAFC", LIGHT_THEME_QSS)

        # 测试信号接收
        received = []
        tm.theme_changed.connect(lambda mode, is_dark: received.append((mode, is_dark)))

        # 切换为白色模式
        tm.apply_theme("light")
        self.assertEqual(tm.get_mode(), "light")
        self.assertFalse(tm.is_dark())
        self.assertEqual(global_settings.get("app_theme"), "light")
        self.assertGreater(len(received), 0)
        self.assertEqual(received[-1], ("light", False))

        # 切换为黑色模式
        tm.apply_theme("dark")
        self.assertEqual(tm.get_mode(), "dark")
        self.assertTrue(tm.is_dark())
        self.assertEqual(global_settings.get("app_theme"), "dark")
        self.assertEqual(received[-1], ("dark", True))

        # 切换为系统模式
        tm.apply_theme("system")
        self.assertEqual(tm.get_mode(), "system")
        self.assertIn(tm.is_dark(), (True, False))
        self.assertEqual(received[-1][0], "system")

    def test_markdown_theme_rendering(self):
        from core.text_utils import render_markdown_to_html

        sample_md = "# 标题\n| 字段 | 值 |\n|---|---|\n| 测试 | 成功 |\n`code`"

        # 显式测试深色模式渲染
        dark_html = render_markdown_to_html(sample_md, is_dark=True)
        self.assertIn("#E4E4E7", dark_html)
        self.assertIn("#3F3F46", dark_html)
        self.assertIn("#18181B", dark_html)

        # 显式测试浅色模式渲染
        light_html = render_markdown_to_html(sample_md, is_dark=False)
        self.assertIn("#0F172A", light_html)
        self.assertIn("#CBD5E1", light_html)
        self.assertIn("#F8FAFC", light_html)

if __name__ == "__main__":
    unittest.main()

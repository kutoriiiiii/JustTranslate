# -*- coding: utf-8 -*-
"""Unit tests for DictionaryParser and DictionaryCardPanel component."""

import unittest
from PySide6.QtWidgets import QApplication
from core.dictionary_parser import (
    parse_dictionary_output,
    DictionaryEntry,
    DefinitionItem,
    ExampleItem
)
from ui.components.dictionary_card_panel import DictionaryCardPanel


app = QApplication.instance() or QApplication([])


class TestDictionaryParser(unittest.TestCase):

    def test_parse_empty(self):
        entry = parse_dictionary_output("")
        self.assertEqual(entry.word, "")
        self.assertEqual(len(entry.definitions), 0)
        self.assertEqual(len(entry.examples), 0)

        entry_none = parse_dictionary_output(None)
        self.assertEqual(entry_none.word, "")

    def test_parse_standard_tagged_protocol(self):
        sample = (
            "[WORD] ephemeral\n"
            "[PRON] /ɪˈfem.ər.əl/\n"
            "[DEFS]\n"
            "- adj. 短暂的，转瞬即逝的；仅生存一天的\n"
            "- n. 短命的事物；仅存活一日的植物或昆虫\n"
            "[EXAMPLES]\n"
            "• Fame in the modern world is fleeting and ephemeral. | 现代社会的声名短暂而转瞬即逝。\n"
            "• ephemeral streams in the desert —— 沙漠地区的季节性短暂溪流\n"
            "[PHRASES] ephemeral pleasure, ephemeral art\n"
            "[SYNONYMS] fleeting, transient, momentary\n"
            "[ANTONYMS] permanent, eternal, enduring\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertTrue(entry.is_structured)
        self.assertEqual(entry.word, "ephemeral")
        self.assertEqual(entry.pronunciation, "/ɪˈfem.ər.əl/")
        
        self.assertEqual(len(entry.definitions), 2)
        self.assertEqual(entry.definitions[0].pos, "adj.")
        self.assertEqual(entry.definitions[0].meaning, "短暂的，转瞬即逝的；仅生存一天的")
        self.assertEqual(entry.definitions[1].pos, "n.")
        self.assertEqual(entry.definitions[1].meaning, "短命的事物；仅存活一日的植物或昆虫")

        self.assertEqual(len(entry.examples), 2)
        self.assertEqual(entry.examples[0].source, "Fame in the modern world is fleeting and ephemeral.")
        self.assertEqual(entry.examples[0].target, "现代社会的声名短暂而转瞬即逝。")
        self.assertEqual(entry.examples[1].source, "ephemeral streams in the desert")
        self.assertEqual(entry.examples[1].target, "沙漠地区的季节性短暂溪流")

        self.assertEqual(entry.phrases, ["ephemeral pleasure", "ephemeral art"])
        self.assertEqual(entry.synonyms, ["fleeting", "transient", "momentary"])
        self.assertEqual(entry.antonyms, ["permanent", "eternal", "enduring"])

    def test_parse_bracketed_pos(self):
        sample = (
            "[WORD] run\n"
            "[PRON] /rʌn/\n"
            "[DEFS]\n"
            "1. [v.] 奔跑；运转\n"
            "2. [n.] 跑，跑步；路程\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertEqual(len(entry.definitions), 2)
        self.assertEqual(entry.definitions[0].pos, "v.")
        self.assertEqual(entry.definitions[0].meaning, "奔跑；运转")
        self.assertEqual(entry.definitions[1].pos, "n.")
        self.assertEqual(entry.definitions[1].meaning, "跑，跑步；路程")

    def test_parse_multilingual_entries(self):
        # Chinese Idiom
        cn_sample = (
            "[WORD] 临渊羡鱼\n"
            "[PRON] lín yuān xiàn yú\n"
            "[DEFS]\n"
            "- idiom. 比喻只有愿望而没有切实的行动，无济于事。\n"
            "[EXAMPLES]\n"
            "• 临渊羡鱼，不如退而结网。 | 与其空想，不如付诸实践。\n"
            "[SYNONYMS] 空穴来风, 纸上谈兵\n"
            "[ANTONYMS] 脚踏实地, 付诸行动\n"
        )
        cn_entry = parse_dictionary_output(cn_sample)
        self.assertEqual(cn_entry.word, "临渊羡鱼")
        self.assertEqual(cn_entry.pronunciation, "lín yuān xiàn yú")
        self.assertEqual(cn_entry.definitions[0].pos, "idiom.")
        self.assertEqual(cn_entry.examples[0].target, "与其空想，不如付诸实践。")

        # Japanese Entry
        jp_sample = (
            "[WORD] 桜\n"
            "[PRON] さくら (sakura)\n"
            "[DEFS]\n"
            "- n. 樱花；樱树\n"
            "[EXAMPLES]\n"
            "• 春になると桜が満開になります。 | 到了春天，樱花盛开。\n"
            "[PHRASES] 桜前線, 花見\n"
        )
        jp_entry = parse_dictionary_output(jp_sample)
        self.assertEqual(jp_entry.word, "桜")
        self.assertEqual(jp_entry.pronunciation, "さくら (sakura)")
        self.assertEqual(jp_entry.definitions[0].pos, "n.")
        self.assertEqual(len(jp_entry.phrases), 2)

    def test_pronunciation_deduplication_and_tag_filtering(self):
        sample = (
            "[WORD] 食事をする\n"
            "[PRON] /しょくじをする/ /しょくじをする/\n"
            "[DEFS]\n"
            "- 名詞. 食事をするという行為\n"
            "- 動詞. 食事を摂ること\n"
            "[\n"
            "[EXAMPLES]\n"
            "• 彼は毎日定時に食事をする。 | 他每天按时吃饭。\n"
            "• [PH\n"
            "[PHRASES] 一緒に食事をする, 早く食事をする\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertEqual(entry.word, "食事をする")
        # 验证音标/假名重复输出两遍时自动去重
        self.assertEqual(entry.pronunciation, "/しょくじをする/")
        # 验证 [DEFS] 末尾由于流式中途出现的 "[" 标签碎片被成功过滤
        self.assertEqual(len(entry.definitions), 2)
        self.assertEqual(entry.definitions[0].meaning, "食事をするという行為")
        self.assertEqual(entry.definitions[1].meaning, "食事を摂ること")
        # 验证 [EXAMPLES] 末尾出现的 "• [PH" 标签碎片被成功过滤
        self.assertEqual(len(entry.examples), 1)
        self.assertEqual(entry.examples[0].source, "彼は毎日定時に食事をする。")
        self.assertEqual(entry.examples[0].target, "他每天按时吃饭。")
        self.assertEqual(len(entry.phrases), 2)

    def test_japanese_chinese_example_auto_split(self):
        sample = (
            "[WORD] 食べる\n"
            "[EXAMPLES]\n"
            "• 子供たちは学校で一緒に食事をする。 他每天按时吃饭。\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertEqual(len(entry.examples), 1)
        self.assertEqual(entry.examples[0].source, "子供たちは学校で一緒に食事をする。")
        self.assertEqual(entry.examples[0].target, "他每天按时吃饭。")

    def test_parse_examples_without_delimiter(self):
        # 智能分离无 | 或 —— 分隔符时的英文原句与中文翻译
        sample = (
            "[WORD] experiment\n"
            "[PRON] /ɪkˈsper.ə.mənt/\n"
            "[DEFS]\n- n. 实验\n"
            "[EXAMPLES]\n• The scientists conducted an experiment to study the effects of climate change. 科学家做了一项实验以研究气候变化的影响。\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertEqual(len(entry.examples), 1)
        self.assertEqual(entry.examples[0].source, "The scientists conducted an experiment to study the effects of climate change.")
        self.assertEqual(entry.examples[0].target, "科学家做了一项实验以研究气候变化的影响。")

    def test_parse_fallback_freeform(self):
        sample = "serendipity /ˌserənˈdɪpəti/\nn. 意外发现珍奇事物的本领"
        entry = parse_dictionary_output(sample)
        self.assertTrue(entry.is_structured)
        self.assertEqual(entry.word, "serendipity")
        self.assertEqual(entry.pronunciation, "/ˌserənˈdɪpəti/")
        self.assertEqual(entry.raw_text, sample)
        self.assertEqual(len(entry.definitions), 1)
        self.assertEqual(entry.definitions[0].pos, "n.")
        self.assertEqual(entry.definitions[0].meaning, "意外发现珍奇事物的本领")

    def test_parse_fallback_freeform_unstructured(self):
        sample = "这是一段完全没有词条格式和释义的普通随笔备忘文本。"
        entry = parse_dictionary_output(sample)
        self.assertFalse(entry.is_structured)
        self.assertEqual(len(entry.definitions), 0)
        self.assertEqual(len(entry.examples), 0)

    def test_parse_tweak_user_reported_case(self):
        sample = (
            "[tweak] /twik/\n"
            "[v.] to make small changes to something in order to improve it | 对某物进行微调以使其更好\n"
            "[n.] a small change made to improve something | 为改进某物而做的微小改动\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertTrue(entry.is_structured)
        self.assertEqual(entry.word, "tweak")
        self.assertEqual(entry.pronunciation, "/twik/")
        self.assertEqual(len(entry.definitions), 2)
        self.assertEqual(entry.definitions[0].pos, "v.")
        self.assertEqual(entry.definitions[0].meaning, "to make small changes to something in order to improve it")
        self.assertEqual(entry.definitions[0].meaning_trans, "对某物进行微调以使其更好")
        self.assertEqual(entry.definitions[1].pos, "n.")
        self.assertEqual(entry.definitions[1].meaning, "a small change made to improve something")
        self.assertEqual(entry.definitions[1].meaning_trans, "为改进某物而做的微小改动")


class TestDictionaryCardPanel(unittest.TestCase):

    def setUp(self):
        self.panel = DictionaryCardPanel()

    def tearDown(self):
        self.panel.deleteLater()
        app.processEvents()

    def test_initial_state(self):
        self.assertEqual(self.panel.stack.currentIndex(), 0)  # placeholder
        self.assertEqual(self.panel.lbl_status.text(), "就绪")
        self.assertFalse(self.panel.btn_stop.isEnabled())
        self.assertTrue(self.panel.btn_retry.isEnabled())

    def test_streaming_lifecycle(self):
        # 1. 验证启动流式时直接呈现卡片看板模板，且词头立即展现
        self.panel.start_streaming("ubiquitous")
        self.assertEqual(self.panel.stack.currentIndex(), 1)  # 直接驻留固定卡片模板页面 (index 1)
        self.assertEqual(self.panel.lbl_word.text(), "ubiquitous")
        self.assertTrue(self.panel.btn_stop.isEnabled())
        self.assertFalse(self.panel.btn_retry.isEnabled())

        # 2. 验证增量接收 chunk
        self.panel.append_chunk("[WORD] ubiquitous\n")
        self.panel.append_chunk("[PRON] /juːˈbɪk.wə.təs/\n")
        self.panel.append_chunk("[DEFS]\n- adj. 无所不在的，普遍存在的\n")
        self.assertIn("ubiquitous", self.panel.get_raw_text())

        # 3. 验证流式完成：无页面切换跳跃，直接原地呈现就绪
        self.panel.finish_streaming()
        self.assertEqual(self.panel.stack.currentIndex(), 1)  # 页面保持固定模板 (index 1)
        self.assertFalse(self.panel.btn_stop.isEnabled())
        self.assertTrue(self.panel.btn_retry.isEnabled())
        self.assertEqual(self.panel.lbl_status.text(), "就绪")
        self.assertEqual(self.panel.lbl_pron.text(), "/juːˈbɪk.wə.təs/")
        self.assertGreater(len(self.panel._def_rows), 0)

    def test_panel_render_tweak_freeform(self):
        sample = (
            "[tweak] /twik/\n"
            "[v.] to make small changes to something in order to improve it | 对某物进行微调以使其更好\n"
            "[n.] a small change made to improve something | 为改进某物而做的微小改动\n"
        )
        self.panel.start_streaming("tweak")
        self.panel.finish_streaming(sample)
        self.assertEqual(self.panel.lbl_word.text(), "tweak")
        self.assertEqual(self.panel.lbl_pron.text(), "/twik/")
        self.assertEqual(len(self.panel._def_rows), 2)
        self.assertTrue(self.panel.card_fallback.isHidden())
        self.assertFalse(self.panel.card_defs.isHidden())

    def test_parse_corrupt_word_tag_with_definition(self):
        sample = (
            "[WORD] 修饰；微调 | to make small adjustments to something\n"
            "[PRON] /twiːk/\n"
            "[DEFS]\n"
            "- v. to make small adjustments to something to improve it slightly | v. to modify something in a minor way\n"
            "[EXAMPLES]\n"
            "• She tweaked the settings to optimize performance. | 她微调了设置以优化性能。\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertNotEqual(entry.word, "修饰；微调 | to make small adjustments to something")
        self.assertTrue(entry.is_structured)
        self.assertEqual(entry.pronunciation, "/twiːk/")
        self.assertGreaterEqual(len(entry.definitions), 2)

    def test_panel_render_corrupt_word_tag_safeguard(self):
        sample = (
            "[WORD] 修饰；微调 | to make small adjustments to something\n"
            "[PRON] /twiːk/\n"
            "[DEFS]\n"
            "- v. to make small adjustments to something | 对某物进行微调\n"
        )
        self.panel.start_streaming("tweak")
        self.panel.finish_streaming(sample)
        self.assertEqual(self.panel.lbl_word.text(), "tweak")
        self.assertEqual(self.panel.lbl_pron.text(), "/twiːk/")

    def test_english_to_english_dictionary_prompt(self):
        from config.default_prompts import build_prompt_messages
        # 1. 正常模式：去噪融合后应包含完整的 7 标签且无任何恐吓性“铁律”字眼
        msgs = build_prompt_messages("dictionary", "English", "English", "tweak", eco_mode=False)
        sys_p = msgs[0]["content"]
        usr_p = msgs[1]["content"]
        self.assertNotIn("绝对严禁使用任何英文单词或英文释义", usr_p)
        self.assertNotIn("绝对严禁使用任何英文单词或英文释义", sys_p)
        self.assertNotIn("铁律", sys_p)
        self.assertNotIn("铁律", usr_p)
        self.assertIn("[WORD] tweak", sys_p)
        self.assertIn("tweak", usr_p)
        self.assertIn("[DEFS]", sys_p)
        self.assertIn("[EXAMPLES]", sys_p)
        self.assertIn("[PHRASES]", sys_p)
        self.assertIn("[SYNONYMS]", sys_p)
        self.assertIn("[ANTONYMS]", sys_p)

        # 2. 省钱模式：同具 7 标签黄金结构
        eco_msgs = build_prompt_messages("dictionary", "English", "English", "tweak", eco_mode=True)
        eco_sys = eco_msgs[0]["content"]
        eco_usr = eco_msgs[1]["content"]
        self.assertIn("[WORD] tweak", eco_sys)
        self.assertIn("[EXAMPLES]", eco_sys)
        self.assertNotIn("绝对严禁使用任何英文单词或英文释义", eco_sys)
        self.assertNotIn("铁律", eco_sys)
        self.assertNotIn("铁律", eco_usr)

    def test_fused_dictionary_prompt_details(self):
        from config.default_prompts import build_prompt_messages
        # 验证正常模式详细度引导与无负向噪声
        msgs = build_prompt_messages("dictionary", "English", "Chinese", "tweak", eco_mode=False)
        sys_p = msgs[0]["content"]
        usr_p = msgs[1]["content"]
        self.assertIn("2~4 条", usr_p)
        self.assertIn("2~3 条", usr_p)
        self.assertIn("[WORD] tweak", sys_p)
        self.assertNotIn("最重要铁律", sys_p)
        self.assertNotIn("严禁输出任何问候", sys_p)

        # 验证省钱模式精炼度与无负向噪声
        eco_msgs = build_prompt_messages("dictionary", "English", "Chinese", "tweak", eco_mode=True)
        eco_sys = eco_msgs[0]["content"]
        eco_usr = eco_msgs[1]["content"]
        self.assertIn("1~2条核心释义", eco_usr)
        self.assertIn("[WORD] tweak", eco_sys)
        self.assertNotIn("最重要铁律", eco_sys)

    def test_finish_streaming_empty(self):
        self.panel.start_streaming()
        self.panel.finish_streaming("")
        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertEqual(self.panel.lbl_status.text(), "无结果")

    def test_copy_all_content(self):
        sample = (
            "[WORD] test\n"
            "[PRON] /test/\n"
            "[DEFS]\n- n. 测试\n"
            "[EXAMPLES]\n• This is a test. | 这是一个测试。\n"
        )
        self.panel.finish_streaming(sample)
        # Verify clipboard copying doesn't raise errors
        self.panel._copy_all_content()
        clipboard_text = QApplication.clipboard().text()
        self.assertIn("test", clipboard_text)
        self.assertIn("核心释义", clipboard_text)

    def test_show_error(self):
        self.panel.start_streaming()
        self.panel.show_error("API Connection Timeout")
        self.assertEqual(self.panel.stack.currentIndex(), 1)
        self.assertEqual(self.panel.lbl_status.text(), "出错了")
        self.assertFalse(self.panel.btn_stop.isEnabled())
        self.assertTrue(self.panel.btn_retry.isEnabled())
        self.assertIn("API Connection Timeout", self.panel.lbl_error.text())

    def test_example_copy_and_speak_interaction(self):
        from core.tts_manager import tts_manager
        from PySide6.QtWidgets import QPushButton

        sample = (
            "[WORD] ephemeral\n"
            "[PRON] /ɪˈfem.ər.əl/\n"
            "[DEFS]\n- adj. 短暂的\n"
            "[EXAMPLES]\n• Fame is fleeting and ephemeral. | 声名短暂而转瞬即逝。\n"
        )
        self.panel.finish_streaming(sample)

        # 寻找例句操作按钮
        action_btns = self.panel.findChildren(QPushButton, "dictActionBtn")
        self.assertEqual(len(action_btns), 2)
        btn_speak = action_btns[0]
        btn_copy = action_btns[1]

        # 1. 验证复制例句与视觉反馈
        btn_copy.click()
        copied = QApplication.clipboard().text()
        self.assertIn("Fame is fleeting and ephemeral.", copied)
        self.assertIn("声名短暂而转瞬即逝。", copied)
        self.assertEqual(btn_copy.text(), "✓")
        self.assertEqual(btn_copy.toolTip(), "已复制到剪贴板！")

        # 2. 验证朗读例句与动态状态反馈（参数必须为真实字符串而非布尔值）
        spoken_data = []
        orig_speak = tts_manager.speak
        try:
            tts_manager.speak = lambda txt, lang=None, parent_widget=None: spoken_data.append((txt, lang))
            btn_speak.click()
            self.assertEqual(len(spoken_data), 1)
            spoken_text = spoken_data[0][0]
            self.assertIsInstance(spoken_text, str)
            self.assertNotIsInstance(spoken_text, bool)
            self.assertEqual(spoken_text, "Fame is fleeting and ephemeral.")
            self.assertEqual(btn_speak.text(), "🔊...")

            # 模拟语音播放完成，验证按钮自动还原
            tts_manager.speech_finished.emit()
            self.assertEqual(btn_speak.text(), "🔊")
        finally:
            tts_manager.speak = orig_speak

    def test_word_copy_and_speak_interaction(self):
        from core.tts_manager import tts_manager
        from PySide6.QtWidgets import QPushButton

        sample = (
            "[WORD] ephemeral\n"
            "[PRON] /ɪˈfem.ər.əl/\n"
            "[DEFS]\n- adj. 短暂的\n"
        )
        self.panel.finish_streaming(sample)

        # 直接使用常驻词头操作按钮
        btn_speak_word = self.panel.btn_speak_word
        btn_copy_word = self.panel.btn_copy_word

        self.assertIsNotNone(btn_speak_word)
        self.assertIsNotNone(btn_copy_word)

        # 1. 测试复制词头
        btn_copy_word.click()
        app.processEvents()
        import time
        for _ in range(10):
            if QApplication.clipboard().text() == "ephemeral":
                break
            time.sleep(0.02)
            app.processEvents()
        self.assertEqual(QApplication.clipboard().text(), "ephemeral")
        self.assertEqual(btn_copy_word.text(), "✓ 已复制")

        # 2. 测试朗读词头
        spoken_data = []
        orig_speak = tts_manager.speak
        try:
            tts_manager.speak = lambda txt, lang=None, parent_widget=None: spoken_data.append((txt, lang))
            btn_speak_word.click()
            self.assertEqual(len(spoken_data), 1)
            self.assertEqual(spoken_data[0][0], "ephemeral")
            self.assertEqual(btn_speak_word.text(), "⏹ 停止朗读")

            # 模拟播放完成
            tts_manager.speech_finished.emit()
            self.assertEqual(btn_speak_word.text(), "🔊 朗读发音")
        finally:
            tts_manager.speak = orig_speak

    def test_header_buttons_uniform_size_and_object_name(self):
        btn_speak = self.panel.btn_speak_word
        btn_copy = self.panel.btn_copy_word
        # 验证具有统一的专用 objectName
        self.assertEqual(btn_speak.objectName(), "dictHeaderBtn")
        self.assertEqual(btn_copy.objectName(), "dictHeaderBtn")
        # 验证两者固定高度完全一致 (26px)
        self.assertEqual(btn_speak.height(), 26)
        self.assertEqual(btn_copy.height(), 26)

    def test_layout_shrink_when_items_decrease(self):
        # 模拟流式阶段 1：解析出 3 条例句与 3 条释义
        chunk_1 = (
            "[WORD] test\n"
            "[DEFS]\n- n. 释义1\n- v. 释义2\n- adj. 释义3\n"
            "[EXAMPLES]\n• Example 1 | 例句1\n• Example 2 | 例句2\n• Example 3 | 例句3\n"
        )
        self.panel.start_streaming()
        self.panel.append_chunk(chunk_1)
        self.panel._apply_progressive_update(is_final=False)
        self.assertEqual(len(self.panel._def_rows), 3)
        self.assertEqual(len(self.panel._example_rows), 3)

        # 模拟流式阶段 2：内容收敛/标签闭合后，释义和例句减少为 2 条
        chunk_2 = (
            "[WORD] test\n"
            "[DEFS]\n- n. 释义1\n- v. 释义2\n"
            "[EXAMPLES]\n• Example 1 | 例句1\n• Example 2 | 例句2\n"
        )
        self.panel.finish_streaming(chunk_2)
        # 验证多余的控件被安全销毁，列表与界面控件数收缩为 2
        self.assertEqual(len(self.panel._def_rows), 2)
        self.assertEqual(len(self.panel._example_rows), 2)
        self.assertEqual(self.panel.defs_content_layout.count(), 2)
        self.assertEqual(self.panel.examples_content_layout.count(), 2)

    def test_japanese_output_language_detection(self):
        sample_jp = (
            "[WORD] 朗读\n"
            "[PRON] /りょうどく/\n"
            "[DEFS]\n- 動詞. 朗读，诵读\n"
            "[EXAMPLES]\n• 彼は毎日詩を朗読する。 | 他每天朗诵诗歌。\n"
        )
        self.panel.finish_streaming(sample_jp)
        # 1. 明确设置目标语言为 Japanese 时，纯汉字词头（如 "朗读" 或 "食事"）必须严格发音为 Japanese，绝不默认中文！
        self.panel.set_target_language("Japanese")
        self.assertEqual(self.panel.get_output_language("朗读"), "Japanese")
        self.assertEqual(self.panel.get_output_language("食事"), "Japanese")
        self.assertEqual(self.panel.get_output_language("彼は毎日詩を朗読する。"), "Japanese")

        # 2. 目标语言为 English 时严格发音为 English
        self.panel.set_target_language("English")
        self.assertEqual(self.panel.get_output_language("read"), "English")

        # 3. 目标语言为 Auto 时，依据平假名注音智能判定为 Japanese
        self.panel.set_target_language("Auto")
        self.assertEqual(self.panel.get_output_language("りょうどく"), "Japanese")
        self.assertEqual(self.panel.get_output_language("朗读"), "Japanese")

    def test_dual_language_definitions_parsing(self):
        sample_dual = (
            "[WORD] experiment\n"
            "[PRON] /ɪkˈsper.ə.mənt/\n"
            "[DEFS]\n"
            "- n. a scientific procedure undertaken to make a discovery | 科学实验，尝试\n"
            "- v. perform a scientific procedure —— 进行科学实验\n"
            "- adj. experimental in nature 具有实验性质的\n"
        )
        entry = parse_dictionary_output(sample_dual)
        self.assertEqual(len(entry.definitions), 3)

        # 1. 验证以 "|" 分隔的标准双语释义
        self.assertEqual(entry.definitions[0].pos, "n.")
        self.assertEqual(entry.definitions[0].meaning, "a scientific procedure undertaken to make a discovery")
        self.assertEqual(entry.definitions[0].meaning_trans, "科学实验，尝试")

        # 2. 验证以 "——" 分隔的容错双语释义
        self.assertEqual(entry.definitions[1].pos, "v.")
        self.assertEqual(entry.definitions[1].meaning, "perform a scientific procedure")
        self.assertEqual(entry.definitions[1].meaning_trans, "进行科学实验")

        # 3. 验证无分隔符西文+中文智能分离
        self.assertEqual(entry.definitions[2].pos, "adj.")
        self.assertEqual(entry.definitions[2].meaning, "experimental in nature")
        self.assertEqual(entry.definitions[2].meaning_trans, "具有实验性质的")

    def test_dual_language_ui_rendering_and_copy(self):
        sample_dual = (
            "[WORD] experiment\n"
            "[PRON] /ɪkˈsper.ə.mənt/\n"
            "[DEFS]\n"
            "- n. scientific test | 科学实验\n"
            "- v. do tests\n"
        )
        self.panel.finish_streaming(sample_dual)
        self.assertEqual(len(self.panel._def_rows), 2)

        # 1. 检查双语行的控件内容与可见状态
        row0 = self.panel._def_rows[0]
        self.assertEqual(row0.lbl_pos.text(), "n.")
        self.assertEqual(row0.lbl_meaning.text(), "scientific test")
        self.assertEqual(row0.lbl_trans.text(), "科学实验")
        self.assertFalse(row0.lbl_trans.isHidden())

        # 2. 检查单语行（无翻译）时副行隐藏
        row1 = self.panel._def_rows[1]
        self.assertEqual(row1.lbl_pos.text(), "v.")
        self.assertEqual(row1.lbl_meaning.text(), "do tests")
        self.assertEqual(row1.lbl_trans.text(), "")
        self.assertTrue(row1.lbl_trans.isHidden())

        # 3. 验证 _copy_all_content 包含双语释义
        self.panel._copy_all_content()
        clipboard_text = QApplication.clipboard().text()
        self.assertIn("n. scientific test | 科学实验", clipboard_text)
        self.assertIn("v. do tests", clipboard_text)

    def test_japanese_chinese_defs_and_stray_pipe(self):
        sample = (
            "[WORD] 食べる\n"
            "[PRON] /たべる/\n"
            "[DEFS]\n"
            "- 動詞. 食物を口に入れて噛んで飲み込むこと | 吃，进食\n"
            "- 動詞. 会食したり食事を共にしたりすること | 吃饭，进餐\n"
            "[EXAMPLES]\n"
            "- 子供たちは学校で毎日食べる | 孩子们每天在学校吃饭。\n"
            "| 孩子们每天在学校进食。\n"
            "- 友達と一緒に食べるのが楽しい | 和朋友一起吃饭很开心。\n"
            "[PHRASES]\n"
            "- 一緒に食べる | 一起吃饭\n"
            "[SYNONYMS]\n"
            "- 食事をする | 进餐，吃饭\n"
            "[ANTONYMS]\n"
            "- 食べない | 不吃\n"
        )
        entry = parse_dictionary_output(sample)
        self.assertEqual(entry.word, "食べる")
        self.assertEqual(entry.pronunciation, "/たべる/")
        self.assertEqual(len(entry.definitions), 2)
        self.assertEqual(entry.definitions[0].pos, "動詞.")
        self.assertEqual(entry.definitions[0].meaning, "食物を口に入れて噛んで飲み込むこと")
        self.assertEqual(entry.definitions[0].meaning_trans, "吃，进食")
        self.assertEqual(entry.definitions[1].pos, "動詞.")
        self.assertEqual(entry.definitions[1].meaning, "会食したり食事を共にしたりすること")
        self.assertEqual(entry.definitions[1].meaning_trans, "吃饭，进餐")

        # 验证行首 stray pipe 不会被当作独立例句入库
        self.assertEqual(len(entry.examples), 2)
        self.assertEqual(entry.examples[0].source, "子供たちは学校で毎日食べる")
        self.assertEqual(entry.examples[0].target, "孩子们每天在学校吃饭。")
        self.assertEqual(entry.examples[1].source, "友達と一緒に食べるのが楽しい")
        self.assertEqual(entry.examples[1].target, "和朋友一起吃饭很开心。")



class TestFlowLayout(unittest.TestCase):

    def test_flow_layout_wrapping_and_sizing(self):
        from ui.components.flow_layout import FlowLayout
        from PySide6.QtWidgets import QWidget, QLabel

        w = QWidget()
        flow = FlowLayout(w, margin=4, h_spacing=6, v_spacing=6)
        for i in range(8):
            lbl = QLabel(f"Very Long Phrase Chip Item Number {i}")
            flow.addWidget(lbl)

        self.assertEqual(flow.count(), 8)
        self.assertTrue(flow.hasHeightForWidth())

        # 宽屏单行/双行高度
        h_wide = flow.heightForWidth(1200)
        # 窄屏必须自动多行折叠，高度应当明显大于宽屏高度
        h_narrow = flow.heightForWidth(300)
        self.assertGreater(h_narrow, h_wide)

        # 最小宽度绝不会被8个长短语无限撑大到800px以上
        min_size = flow.minimumSize()
        self.assertLess(min_size.width(), 400)


if __name__ == '__main__':
    unittest.main()



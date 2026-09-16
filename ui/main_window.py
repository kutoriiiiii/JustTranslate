# -*- coding: utf-8 -*-
"""Main application window connecting UI components and LLM stream pipeline with independent mode workspaces, geometry persistence, and system tray integration."""

import time
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, 
    QMessageBox, QApplication, QStackedWidget
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence, QShortcut
from config.settings import settings
from config.default_prompts import build_prompt_messages
from core.llm_client import LLMClient
from core.stream_worker import StreamWorker
from core.ocr_client import OCRClient, check_ocr_capability
from core.sentence_aligner import split_sentences_with_spans, map_sentence_index
from core.pipeline_worker import PipelineWorker
from core.lang_detector import detect_language, suggest_target_language
from core.text_utils import extract_polished_body
from core.history_manager import history_manager
from ui.components.control_bar import ControlBar
from ui.components.input_panel import InputPanel
from ui.components.output_panel import OutputPanel
from ui.components.settings_dialog import SettingsDialog
from ui.components.history_dialog import HistoryDialog
from ui.components.tray_icon import AppTrayIcon
from ui.components.balanced_splitter import BalancedSplitter
from ui.components.dictionary_card_panel import DictionaryCardPanel

MODE_CONFIGS = {
    "translate": {
        "input_title": "翻译原文",
        "input_placeholder": "在此处输入或粘贴需要翻译的文本...",
        "output_title": "译文展示",
        "copy_btn_text": "📋 复制译文",
        "copy_tooltip": "复制完整译文结果",
        "copy_extractor": None
    },
    "polish": {
        "input_title": "待润色原文",
        "input_placeholder": "在此处输入需要润色优化的文本（保持同语言润色，不会被翻译）...",
        "output_title": "润色结果与优化要点",
        "copy_btn_text": "📋 复制润色正文",
        "copy_tooltip": "只复制润色后的纯净正文，不复制下方的优化要点说明",
        "copy_extractor": extract_polished_body
    },
    "dictionary": {
        "input_title": "词汇/短语查询",
        "input_placeholder": "在此处输入需要查询的单词、成语或短语（如 ephemeral, 斟酌, 桜）...",
        "output_title": "词典释义与例句",
        "copy_btn_text": "📋 复制释义",
        "copy_tooltip": "复制词典释义结果",
        "copy_extractor": None
    }
}

class MainWindow(QMainWindow):
    """Main window with independent input and output workspaces for each mode."""

    MODES = ["translate", "polish", "dictionary"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Just Translate - 智能翻译、润色与词典工作台")

        self.input_panels = {}
        self.output_panels = {}
        self.workers = {m: None for m in self.MODES}
        self._current_task_ids = {m: 0 for m in self.MODES}
        self._request_snapshots = {m: None for m in self.MODES}
        self._task_metadata = {}
        self.tray_icon = None
        self._is_quitting = False

        self._init_ui()
        self._restore_window_geometry()
        self._init_tray_icon()
        self._init_shortcuts()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. 顶部控制栏
        self.control_bar = ControlBar(self)
        self.control_bar.mode_changed.connect(self._on_mode_changed)
        self.control_bar.swap_requested.connect(self._on_swap_languages)
        self.control_bar.open_history_requested.connect(self._open_history)
        self.control_bar.open_settings_requested.connect(self._open_settings)
        main_layout.addWidget(self.control_bar)

        # 2. 中间分栏：使用防塌陷且支持双击 1:1 重置的 BalancedSplitter
        self.splitter = BalancedSplitter(Qt.Horizontal, self)

        self.input_stack = QStackedWidget(self)
        self.input_stack.setMinimumWidth(280)
        self.output_stack = QStackedWidget(self)
        self.output_stack.setMinimumWidth(280)

        # 为翻译、润色、词典分别创建完全独立的输入和输出面板
        for mode in self.MODES:
            cfg = MODE_CONFIGS[mode]
            is_translate = (mode == "translate")

            in_p = InputPanel(self, title=cfg["input_title"], placeholder=cfg["input_placeholder"], mode=mode)
            in_p.submit_requested.connect(lambda text, img, m=mode: self._start_generation(text, m, img))
            in_p.user_text_changed.connect(lambda txt, m=mode: self._on_user_text_changed(txt, m))
            self.input_panels[mode] = in_p
            self.input_stack.addWidget(in_p)

            if mode == "dictionary":
                out_p = DictionaryCardPanel(self, title=cfg["output_title"])
            else:
                out_p = OutputPanel(
                    self, 
                    title=cfg["output_title"],
                    copy_btn_text=cfg.get("copy_btn_text", "📋 复制结果"),
                    copy_extractor=cfg.get("copy_extractor", None),
                    copy_tooltip=cfg.get("copy_tooltip", ""),
                    show_extra_actions=is_translate,
                    mode=mode
                )
            out_p.stop_requested.connect(lambda m=mode: self._on_stop(m))
            out_p.retry_requested.connect(lambda m=mode: self._on_retry(m))
            out_p.format_changed.connect(self._on_format_changed_sync)

            if is_translate:
                out_p.one_click_polish_requested.connect(self._on_one_click_polish)
                out_p.one_click_back_translate_requested.connect(self._on_one_click_back_translate)

            # 逐句对照与双向高亮连接
            in_p.sentence_selected.connect(lambda idx, txt, total, m=mode: self._on_input_sentence_selected(idx, txt, total, m))
            out_p.sentence_selected.connect(lambda idx, txt, total, m=mode: self._on_output_sentence_selected(idx, txt, total, m))
            # 单句独立翻译连接
            in_p.translate_sentence_requested.connect(lambda idx, txt, m=mode: self._open_sentence_translate_dialog(idx, txt, m, is_source=True))
            out_p.translate_sentence_requested.connect(lambda idx, txt, m=mode: self._open_sentence_translate_dialog(idx, txt, m, is_source=False))

            self.output_panels[mode] = out_p
            self.output_stack.addWidget(out_p)

        self.splitter.addWidget(self.input_stack)
        self.splitter.addWidget(self.output_stack)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.splitter, 1)

        # 恢复上次选中的模式视图，确保控制栏高亮与主页面堆栈 100% 严格一致
        last_mode = settings.get("last_mode", "translate")
        self.control_bar.set_mode(last_mode, emit_signal=False)
        self._on_mode_changed(last_mode)

    def _init_shortcuts(self):
        """Initializes global window hotkeys."""
        self.shortcut_history = QShortcut(QKeySequence("Ctrl+H"), self)
        self.shortcut_history.activated.connect(self._open_history)

    def _init_tray_icon(self):
        """Initializes system tray icon and attaches callbacks."""
        if not settings.get("enable_system_tray", True):
            return

        icon_path = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
        self.tray_icon = AppTrayIcon(self, icon_path=icon_path)
        self.tray_icon.restore_window_requested.connect(self._toggle_window_visibility)
        self.tray_icon.mode_switch_requested.connect(self._on_tray_switch_mode)
        self.tray_icon.open_settings_requested.connect(self._open_settings)
        self.tray_icon.quit_requested.connect(self._force_quit_app)
        self.tray_icon.show()

    def _restore_window_geometry(self):
        """Restores window size, position, and splitter layout from settings with multi-screen bounds check."""
        geo = settings.get("window_geometry", {})
        is_max = geo.get("maximized", False)

        width = geo.get("width", 1050)
        height = geo.get("height", 680)
        x = geo.get("x", -1)
        y = geo.get("y", -1)

        width = max(width, 640)
        height = max(height, 420)
        self.setMinimumSize(640, 420)
        self.resize(width, height)

        if x >= 0 and y >= 0:
            screen = QApplication.screenAt(QPoint(x, y))
            if screen:
                self.move(x, y)
            else:
                self._center_on_screen()
        else:
            self._center_on_screen()

        # 恢复分栏比例（若有效且满足两栏最小宽度），否则默认按当前窗口宽度对等均分
        splitter_sizes = geo.get("splitter_sizes", None)
        if (
            splitter_sizes 
            and isinstance(splitter_sizes, list) 
            and len(splitter_sizes) == 2 
            and splitter_sizes[0] >= 280 
            and splitter_sizes[1] >= 280
        ):
            self.splitter.setSizes(splitter_sizes)
        else:
            avail = max(560, width - 24 - 6)
            half = avail // 2
            self.splitter.setSizes([half, avail - half])

        if is_max:
            self.showMaximized()

    def _save_window_geometry(self):
        """Saves current window size, position, and splitter balance to persistent settings."""
        is_max = self.isMaximized()
        geo_dict = {
            "maximized": is_max
        }
        old_geo = settings.get("window_geometry", {})
        if not is_max and not self.isMinimized():
            rect = self.geometry()
            geo_dict.update({
                "x": rect.x(),
                "y": rect.y(),
                "width": rect.width(),
                "height": rect.height()
            })
        else:
            geo_dict.update({
                "x": old_geo.get("x", -1),
                "y": old_geo.get("y", -1),
                "width": old_geo.get("width", 1050),
                "height": old_geo.get("height", 680)
            })

        # 持久化当前左右分栏比例（仅在两栏均满足最小宽度约束时保存）
        current_sizes = self.splitter.sizes()
        if len(current_sizes) == 2 and current_sizes[0] >= 280 and current_sizes[1] >= 280:
            geo_dict["splitter_sizes"] = current_sizes
        elif "splitter_sizes" in old_geo:
            geo_dict["splitter_sizes"] = old_geo["splitter_sizes"]

        settings.set("window_geometry", geo_dict)

    def _center_on_screen(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = (screen_geo.width() - self.width()) // 2
        y = (screen_geo.height() - self.height()) // 2
        self.move(x, y)

    def _toggle_window_visibility(self):
        """Toggles window visibility from tray icon click."""
        if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def _on_tray_switch_mode(self, mode: str):
        """Switches workspace mode from tray menu."""
        self.control_bar.set_mode(mode, emit_signal=True)
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _force_quit_app(self):
        """Forces app to quit completely, bypassing minimize-to-tray."""
        self._is_quitting = True
        self._save_window_geometry()
        for worker in self.workers.values():
            if worker and worker.isRunning():
                worker.abort()
                worker.wait(500)
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_updated.connect(self._on_settings_updated)
        dialog.exec()

    def _open_history(self):
        dialog = HistoryDialog(self)
        dialog.import_requested.connect(self._handle_import_history)
        dialog.exec()

    def _handle_import_history(self, record: dict):
        """Imports a chosen history record back into the corresponding workspace."""
        target_mode = record.get("mode", "translate")
        self.control_bar.set_mode(target_mode, emit_signal=True)

        in_p = self.input_panels.get(target_mode)
        if in_p:
            in_p.set_text(record.get("input_text", ""))

        src = record.get("source_lang")
        tgt = record.get("target_lang")
        if src and tgt:
            self.control_bar.set_languages(src, tgt)

        out_p = self.output_panels.get(target_mode)
        if out_p:
            out_p.finish_streaming(record.get("output_text", ""))
            out_p.set_stale_warning(False)

        # 同步快照，避免历史记录导入被误判为修改
        self._request_snapshots[target_mode] = record.get("input_text", "")

    def _on_user_text_changed(self, current_text: str, mode: str):
        """Monitors user edits to current input text and updates stale warning accordingly."""
        snapshot = self._request_snapshots.get(mode)
        out_p = self.output_panels.get(mode)
        if not out_p:
            return
        if snapshot is not None:
            if current_text != snapshot:
                out_p.set_stale_warning(True)
            else:
                out_p.set_stale_warning(False)

    def _on_format_changed_sync(self, fmt: str):
        """Synchronizes format selection across all mode output panels."""
        for p in self.output_panels.values():
            p.set_format(fmt)

    def _on_settings_updated(self):
        self.control_bar.reload_profiles()
        self.control_bar.sync_eco_mode()
        current_fmt = settings.get("output_format", "markdown")
        for p in self.output_panels.values():
            p.set_format(current_fmt)

    def _on_mode_changed(self, mode: str):
        if mode in self.MODES:
            idx = self.MODES.index(mode)
            self.input_stack.setCurrentIndex(idx)
            self.output_stack.setCurrentIndex(idx)
            for m, p in self.input_panels.items():
                p.set_mode(m)
            if self.control_bar.get_current_mode() != mode:
                self.control_bar.set_mode(mode, emit_signal=False)
            if mode in self.input_panels:
                self.input_panels[mode].editor.setFocus()

    def _on_swap_languages(self):
        mode = self.control_bar.get_current_mode()
        if mode == "polish":
            return

        src_lang, target_lang = self.control_bar.get_languages()
        curr_in_p = self.input_panels.get(mode)
        curr_out_p = self.output_panels.get(mode)
        in_text = curr_in_p.get_text().strip() if curr_in_p else ""
        out_text = curr_out_p.get_raw_text().strip() if curr_out_p else ""

        if src_lang == "Auto":
            if in_text:
                real_src = detect_language(in_text)
            else:
                real_src = "Chinese" if target_lang != "Chinese" else "English"
        else:
            real_src = src_lang

        new_src = target_lang
        new_target = real_src
        if new_src == new_target:
            new_target = "Chinese" if new_src != "Chinese" else "English"

        self.control_bar.set_languages(new_src, new_target)

        if out_text:
            curr_in_p.set_text(out_text)
            curr_out_p.start_streaming()
            curr_out_p.finish_streaming("")

    def _on_one_click_polish(self, translated_text: str):
        """Imports current translation result into polish mode and immediately executes polishing."""
        if not translated_text.strip():
            return

        # 1. 确定译文的实际语言（润色应针对译文文本自身语言）
        src_lang, target_lang = self.control_bar.get_languages()
        if target_lang and target_lang != "Auto":
            polish_lang = target_lang
        else:
            polish_lang = detect_language(translated_text)

        # 2. 将控制栏语言更新为译文本身的语言
        self.control_bar.set_languages(polish_lang, polish_lang)

        # 3. 切换至润色模式
        self.control_bar.set_mode("polish", emit_signal=True)

        # 4. 回填润色输入框并启动流式生成
        polish_in = self.input_panels.get("polish")
        if polish_in:
            polish_in.set_text(translated_text.strip())
            self._start_generation(translated_text.strip(), "polish")

    def _on_one_click_back_translate(self, translated_text: str):
        """Reverses language pair and translates current output back to original source language."""
        if not translated_text.strip():
            return

        # 保持在翻译模式
        self.control_bar.set_mode("translate", emit_signal=True)

        src_lang, target_lang = self.control_bar.get_languages()
        in_p = self.input_panels.get("translate")
        original_in_text = in_p.get_text().strip() if in_p else ""

        if src_lang == "Auto":
            real_src = detect_language(original_in_text) if original_in_text else "Chinese"
        else:
            real_src = src_lang

        real_target = target_lang
        if real_target == "Auto":
            real_target = detect_language(translated_text)

        new_src = real_target
        new_target = real_src
        if new_src == new_target:
            new_target = "Chinese" if new_src != "Chinese" else "English"

        # 设定对调后的语言并写入输入框
        self.control_bar.set_languages(new_src, new_target)
        if in_p:
            in_p.set_text(translated_text.strip())

        # 立即启动回译流式生成
        self._start_generation(translated_text.strip(), "translate")

    def _on_retry(self, mode: str):
        input_panel = self.input_panels.get(mode)
        if input_panel:
            text = input_panel.get_text().strip()
            img = input_panel.current_image
            if text or img:
                self._start_generation(text, mode, img)

    def _on_stop(self, mode: str):
        worker = self.workers.get(mode)
        if worker and worker.isRunning():
            worker.abort()
        out_p = self.output_panels.get(mode)
        if out_p:
            out_p.stop_streaming()
            out_p.set_status("已停止")
        in_p = self.input_panels.get(mode)
        if in_p:
            in_p.set_enabled(True)
        self.control_bar.api_status.set_ready()

    def _start_generation(self, text: str, mode: str, image_input=None, dict_type: str = "full"):
        if not text.strip() and not image_input:
            return

        in_p = self.input_panels[mode]
        out_p = self.output_panels[mode]

        # 1. 任务 ID 自增，作为当前活跃任务唯一标识
        self._current_task_ids[mode] += 1
        task_id = self._current_task_ids[mode]

        # 2. 异步中止该模式上一次的未完成任务（非阻塞，彻底消除 wait(500) 卡顿）
        prev_worker = self.workers.get(mode)
        if prev_worker and prev_worker.isRunning():
            prev_worker.abort()

        # 3. 记录本次请求的原文快照，并清空旧的过期提示
        self._request_snapshots[mode] = text
        out_p.set_stale_warning(False)

        if mode == "dictionary":
            if dict_type == "syn_ant":
                out_p.set_title("同义词与反义词")
            else:
                out_p.set_title("词典释义与例句")

        # 获取活跃 Profile
        profile = settings.get_active_profile()
        base_url = profile.get("base_url", "").strip()
        api_key = profile.get("api_key", "").strip()
        model = profile.get("model", "default").strip()

        if not base_url:
            QMessageBox.warning(self, "配置缺失", "当前模型配置未设置 Base URL，请点击右上角【设置】进行配置！")
            return

        # 记录本次任务元数据以供记忆入库
        self._task_metadata[mode] = {
            "start_time": time.time(),
            "input_text": text,
            "model": model,
            "src_lang": "",
            "target_lang": "",
            "ttft_ms": 0.0,
            "speed_tok_s": 0.0,
            "duration_s": 0.0
        }

        # 检查 OCR 客户端（如果有传入图片）
        ocr_client = None
        if image_input:
            has_ocr, ocr_msg, ocr_url, ocr_key, ocr_m = check_ocr_capability(profile, settings.data)
            if not has_ocr:
                QMessageBox.warning(
                    self,
                    "OCR 识图能力提示",
                    f"⚠️ 当前配置的模型【{model}】不具备 OCR 识图功能，无法识别图片中的文字。\n\n"
                    f"💡 建议操作：\n"
                    f"1. 前往「⚙ 设置 ➔ 模型服务」，将当前配置切换为支持多模态视觉的模型（如 GPT-4o、GLM-4V、Qwen-VL 等）；\n"
                    f"2. 或在当前配置中填入专门的「OCR 识图模型」（或开启本地 OCR 服务后重试）。"
                )
                out_p.set_status("当前模型不支持 OCR 识图")
                in_p.set_enabled(True)
                return

            ocr_client = OCRClient(
                base_url=ocr_url,
                api_key=ocr_key,
                model=ocr_m,
                timeout=30.0,
                max_retries=settings.get("max_retries", 2)
            )

        src_lang, target_lang = self.control_bar.get_languages()
        custom_prompts = settings.get("custom_prompts", {})
        custom_prompt = custom_prompts.get(mode, "")

        def build_messages_for_text(resolved_text: str) -> list:
            if mode == "polish":
                detected = detect_language(resolved_text)
                # 润色模式核心逻辑：输入中文则输出中文润色，输入英文则输出英文润色，严格同语言闭环
                d_src = detected
                d_target = detected
                self.control_bar.set_languages(d_src, d_target)
            else:
                if src_lang == "Auto":
                    d_src = detect_language(resolved_text)
                    if target_lang and target_lang != d_src:
                        d_target = target_lang
                    else:
                        d_target = suggest_target_language(d_src)
                else:
                    d_src = src_lang
                    d_target = target_lang

            # 补充记录识别出的真实语言与完整文本
            if mode in self._task_metadata:
                self._task_metadata[mode]["src_lang"] = d_src
                self._task_metadata[mode]["target_lang"] = d_target
                if not self._task_metadata[mode]["input_text"]:
                    self._task_metadata[mode]["input_text"] = resolved_text

            output_fmt = settings.get("output_format", "markdown")
            eco_mode = bool(settings.get("eco_mode", False))

            return build_prompt_messages(
                mode=mode,
                src_lang=d_src,
                target_lang=d_target,
                text=resolved_text,
                custom_system_prompt=custom_prompt,
                output_format=output_fmt,
                eco_mode=eco_mode,
                dict_type=dict_type
            )

        # 开启该模式专属面板的流式展示
        out_p.start_streaming(query_word=text.strip())
        if image_input:
            out_p.set_status("正在准备图片识别与联动翻译...")
        else:
            out_p.set_status(f"正在向 [{profile.get('name')}] 请求...")
        
        # 允许在生成过程中编辑原文或再次提交（取消并替换），保持输入面板可用
        in_p.set_enabled(True)

        client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=30.0,
            max_retries=settings.get("max_retries", 2)
        )
        temperature = float(settings.get("temperature", 0.3))

        worker = PipelineWorker(
            llm_client=client,
            messages_builder_fn=build_messages_for_text,
            image_input=image_input,
            ocr_client=ocr_client,
            raw_text=text,
            temperature=temperature
        )
        self.workers[mode] = worker

        # 信号绑定该模式的专用控件，携带 task_id 进行绝对任务归属校验
        worker.ocr_text_extracted.connect(lambda extracted, m=mode, tid=task_id: self._handle_ocr_extracted(extracted, m, tid))
        worker.token_received.connect(lambda chunk, m=mode, tid=task_id: self._handle_worker_token(chunk, m, tid))
        worker.status_changed.connect(lambda status, m=mode, tid=task_id: self._handle_worker_status(status, m, tid))
        worker.error_occurred.connect(lambda err, m=mode, tid=task_id: self._handle_worker_error(err, m, tid))
        worker.completed.connect(lambda final_txt, m=mode, tid=task_id: self._handle_worker_completed(final_txt, m, tid))
        worker.stopped.connect(lambda partial_txt, m=mode, tid=task_id: self._handle_worker_stopped(partial_txt, m, tid))

        # 实时 API 连接状态与速度指标联动
        self.control_bar.api_status.set_connecting()
        worker.metrics_updated.connect(lambda lat, spd, m=mode, tid=task_id: self._handle_metrics_updated(lat, spd, m, tid))
        worker.metrics_completed.connect(lambda lat, spd, m=mode, tid=task_id: self._handle_metrics_completed(lat, spd, m, tid))

        worker.start()

    def _handle_worker_token(self, chunk: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        out_p = self.output_panels.get(mode)
        if out_p:
            out_p.append_chunk(chunk)

    def _handle_worker_status(self, status: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        out_p = self.output_panels.get(mode)
        if out_p:
            out_p.set_status(status)

    def _handle_metrics_updated(self, latency_ms: int, speed: float, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        self.control_bar.api_status.set_streaming(latency_ms, speed)

    def _handle_metrics_completed(self, latency_ms: int, speed: float, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        self.control_bar.api_status.set_ready(latency_ms, speed)
        if mode in self._task_metadata:
            meta = self._task_metadata[mode]
            meta["ttft_ms"] = float(latency_ms)
            meta["speed_tok_s"] = float(speed)
            start_t = meta.get("start_time", time.time())
            meta["duration_s"] = max(0.1, round(time.time() - start_t, 2))

    def _handle_ocr_extracted(self, extracted: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        in_p = self.input_panels.get(mode)
        if in_p:
            in_p.set_text(extracted)
            in_p.clear_image()
        # 更新快照避免 OCR 回填被误认为修改
        self._request_snapshots[mode] = extracted

    def _handle_worker_completed(self, final_text: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        out_p = self.output_panels.get(mode)
        in_p = self.input_panels.get(mode)
        if out_p:
            out_p.finish_streaming(final_text)
        if in_p:
            in_p.set_enabled(True)

        # 检查生成完成时原文是否已被用户修改
        snapshot = self._request_snapshots.get(mode)
        if in_p and snapshot is not None and in_p.get_text() != snapshot:
            if out_p:
                out_p.set_stale_warning(True)
        else:
            if out_p:
                out_p.set_stale_warning(False)

        # 仅对正常完成且有内容的任务写入轻量化记忆库
        if final_text.strip() and mode in self._task_metadata:
            meta = self._task_metadata[mode]
            history_manager.add_record(
                mode=mode,
                source_lang=meta.get("src_lang", ""),
                target_lang=meta.get("target_lang", ""),
                model=meta.get("model", ""),
                input_text=meta.get("input_text", ""),
                output_text=final_text.strip(),
                ttft_ms=meta.get("ttft_ms", 0.0),
                speed_tok_s=meta.get("speed_tok_s", 0.0),
                duration_s=meta.get("duration_s", 0.0)
            )

    def _handle_worker_stopped(self, partial_text: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        out_p = self.output_panels.get(mode)
        in_p = self.input_panels.get(mode)
        if out_p:
            out_p.stop_streaming(partial_text)
            out_p.set_status("已停止")
        if in_p:
            in_p.set_enabled(True)
        self.control_bar.api_status.set_ready()

        # 检查停止时原文是否已被用户修改
        snapshot = self._request_snapshots.get(mode)
        if in_p and snapshot is not None and in_p.get_text() != snapshot:
            if out_p:
                out_p.set_stale_warning(True)

    def _handle_worker_error(self, error_msg: str, mode: str, task_id: int):
        if task_id != self._current_task_ids.get(mode):
            return
        out_p = self.output_panels.get(mode)
        in_p = self.input_panels.get(mode)
        if out_p:
            out_p.show_error(error_msg)
        if in_p:
            in_p.set_enabled(True)
        self.control_bar.api_status.set_error(error_msg)

    def _on_input_sentence_selected(self, src_idx: int, src_text: str, src_total: int, mode: str):
        """Cross-box alignment: highlights corresponding target sentence when input sentence is selected."""
        out_p = self.output_panels.get(mode)
        if not out_p:
            return
        out_text = out_p.get_raw_text()
        out_spans = split_sentences_with_spans(out_text)
        target_total = len(out_spans)
        if target_total > 0:
            mapped_idx = map_sentence_index(src_idx, src_total, target_total)
            out_p.highlight_sentence(mapped_idx)
            out_p.set_status(f"🔍 逐句对照: 原文第 {src_idx + 1}/{src_total} 句 ➔ 译文第 {mapped_idx + 1}/{target_total} 句")

    def _on_output_sentence_selected(self, target_idx: int, target_text: str, target_total: int, mode: str):
        """Cross-box alignment: highlights corresponding source sentence when output sentence is selected."""
        in_p = self.input_panels.get(mode)
        out_p = self.output_panels.get(mode)
        if not in_p:
            return
        in_text = in_p.get_text()
        in_spans = split_sentences_with_spans(in_text)
        src_total = len(in_spans)
        if src_total > 0:
            mapped_idx = map_sentence_index(target_idx, target_total, src_total)
            in_p.highlight_sentence(mapped_idx)
            if out_p:
                out_p.set_status(f"🔍 逐句对照: 译文第 {target_idx + 1}/{target_total} 句 ➔ 原文第 {mapped_idx + 1}/{src_total} 句")

    def _open_sentence_translate_dialog(self, idx: int, text: str, mode: str, is_source: bool = True):
        """Opens mini-dialog to translate a single sentence independently and optionally replace it in output."""
        in_p = self.input_panels.get(mode)
        out_p = self.output_panels.get(mode)
        if not in_p or not out_p:
            return

        src_lang, target_lang = self.control_bar.get_languages()
        profile = self.control_bar.get_current_profile()
        eco_mode = bool(settings.get("eco_mode", False))

        out_spans = split_sentences_with_spans(out_p.get_raw_text())
        in_spans = split_sentences_with_spans(in_p.get_text())

        if is_source:
            sentence_src_text = text
            target_out_idx = map_sentence_index(idx, len(in_spans), len(out_spans)) if out_spans else 0
        else:
            target_out_idx = idx
            mapped_in_idx = map_sentence_index(idx, len(out_spans), len(in_spans)) if in_spans else 0
            sentence_src_text = in_spans[mapped_in_idx].text if in_spans else text

        current_target_text = out_spans[target_out_idx].text if 0 <= target_out_idx < len(out_spans) else ""

        # 智能解析真实的语言对（彻底规避 Auto 导致模型把英文翻译为英文产生“无变化”现象）
        real_src = src_lang
        if real_src == "Auto":
            real_src = detect_language(sentence_src_text)

        real_target = target_lang
        if real_target == "Auto" or real_target == real_src:
            real_target = suggest_target_language(real_src)

        from ui.components.sentence_translate_dialog import SentenceTranslateDialog
        dialog = SentenceTranslateDialog(
            parent=self,
            sentence_index=target_out_idx,
            sentence_text=sentence_src_text,
            src_lang=real_src,
            target_lang=real_target,
            profile=profile,
            current_target_text=current_target_text,
            eco_mode=eco_mode
        )
        dialog.replace_requested.connect(lambda s_idx, new_trans: self._on_sentence_replaced(s_idx, new_trans, mode))
        dialog.exec()

    def _on_sentence_replaced(self, sentence_index: int, new_translated_text: str, mode: str):
        out_p = self.output_panels.get(mode)
        if out_p:
            out_p.replace_sentence_at_index(sentence_index, new_translated_text)
            out_p.set_status(f"✓ 已将第 {sentence_index + 1} 句替换为最新独立译文")

    def closeEvent(self, event):
        self._save_window_geometry()

        if not self._is_quitting and settings.get("minimize_to_tray_on_close", True):
            event.ignore()
            self.hide()
            if not settings.get("tray_notification_shown", False) and self.tray_icon:
                self.tray_icon.notify("Just Translate", "程序已最小化到系统托盘，双击或右键托盘图标可快速唤醒。")
                settings.set("tray_notification_shown", True)
        else:
            for worker in self.workers.values():
                if worker and worker.isRunning():
                    worker.abort()
                    worker.wait(500)
            if self.tray_icon:
                self.tray_icon.hide()
            event.accept()

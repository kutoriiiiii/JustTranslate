# -*- coding: utf-8 -*-
"""Text-to-Speech manager supporting Microsoft Edge Neural TTS with Native OS SAPI fallback."""

import sys
import os
import time
import asyncio
import tempfile
import subprocess
from typing import Optional, Set

from PySide6.QtCore import QObject, Signal, QThread, QUrl, QTimer
from PySide6.QtWidgets import QDialog, QWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from config.settings import settings


# 映射 Just Translate 语种到微软 Edge 高品质神经语音发音人
EDGE_VOICE_MAP = {
    "Chinese": "zh-CN-XiaoxiaoNeural",
    "English": "en-US-JennyNeural",
    "Japanese": "ja-JP-NanamiNeural",
    "Korean": "ko-KR-SunHiNeural",
    "French": "fr-FR-DeniseNeural",
    "German": "de-DE-KatjaNeural",
    "Spanish": "es-ES-ElviraNeural",
    "Russian": "ru-RU-SvetlanaNeural",
    "Portuguese": "pt-BR-FranciscaNeural",
    "Italian": "it-IT-ElsaNeural",
    "Arabic": "ar-SA-ZariyahNeural",
    "Vietnamese": "vi-VN-HoaiMyNeural",
    "Thai": "th-TH-PremwadeeNeural",
    "Indonesian": "id-ID-GadisNeural",
    "Dutch": "nl-NL-ColetteNeural",
    "Turkish": "tr-TR-EmelNeural"
}


class EdgeTTSWorker(QThread):
    """Background thread to fetch Edge Neural TTS audio via async protocol."""
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, text: str, voice: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import edge_tts

        # 网络异常自动重试控制（单次超时上限 30 秒）
        for attempt in range(2):
            if self._is_cancelled:
                return
            try:
                async def _download():
                    communicate = edge_tts.Communicate(self.text, self.voice)
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        output_path = f.name
                    await asyncio.wait_for(communicate.save(output_path), timeout=30.0)
                    return output_path

                temp_audio = asyncio.run(_download())
                if self._is_cancelled:
                    try:
                        os.remove(temp_audio)
                    except Exception:
                        pass
                    return

                self.finished_signal.emit(temp_audio)
                return
            except Exception as e:
                if attempt == 0 and not self._is_cancelled:
                    time.sleep(0.5)
                    continue
                if not self._is_cancelled:
                    self.error_signal.emit(str(e))


class TTSManager(QObject):
    """Central manager for Text-to-Speech synthesis with Edge Neural TTS and SAPI fallback."""

    speech_started = Signal(str)
    speech_finished = Signal()
    speech_error = Signal(str)

    _instance: Optional["TTSManager"] = None

    @classmethod
    def get_instance(cls) -> "TTSManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sapi_voice = None
        self._mac_process = None
        self._is_speaking = False

        # Edge TTS 播放器组件
        self._current_worker: Optional[EdgeTTSWorker] = None
        self._current_temp_file: Optional[str] = None
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        # SAPI / macOS 轮询定时器
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._check_speech_status)

        # 本地已安装语言清单检测
        self._local_languages: Set[str] = set()
        self._init_local_engines()

    def _init_local_engines(self):
        """Initializes native OS voice engines and enumerates locally available languages."""
        if sys.platform == "win32":
            try:
                import win32com.client
                self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                self._detect_windows_local_voices()
            except Exception as e:
                print(f"Failed to initialize Windows SAPI: {e}")
                self._sapi_voice = None
        elif sys.platform == "darwin":
            # macOS 内置多语种 voice 库，默认支持主要语言
            self._local_languages = {"Chinese", "English", "Japanese", "French", "German", "Spanish"}

    def is_sapi_available(self) -> bool:
        """Returns True if native OS speech synthesis is available."""
        return self._sapi_voice is not None or sys.platform == "darwin"

    def _detect_windows_local_voices(self):
        """Inspects installed SAPI voices and maps them to language codes."""
        if not self._sapi_voice:
            return

        try:
            voices = self._sapi_voice.GetVoices()
            for i in range(voices.Count):
                v = voices.Item(i)
                desc = v.GetDescription().lower()

                if any(k in desc for k in ["chinese", "huihui", "yaoyao", "kangkang", "zh-"]):
                    self._local_languages.add("Chinese")
                if any(k in desc for k in ["english", "zira", "david", "en-"]):
                    self._local_languages.add("English")
                if any(k in desc for k in ["japanese", "haruka", "ichiro", "ayumi", "ja-"]):
                    self._local_languages.add("Japanese")
                if any(k in desc for k in ["korean", "heami", "ko-"]):
                    self._local_languages.add("Korean")
                if any(k in desc for k in ["french", "hortense", "paul", "fr-"]):
                    self._local_languages.add("French")
                if any(k in desc for k in ["german", "hedda", "stefan", "de-"]):
                    self._local_languages.add("German")
                if any(k in desc for k in ["spanish", "helena", "laura", "es-"]):
                    self._local_languages.add("Spanish")
                if any(k in desc for k in ["russian", "irina", "pavel", "ru-"]):
                    self._local_languages.add("Russian")
                if any(k in desc for k in ["italian", "elsa", "cosimo", "it-"]):
                    self._local_languages.add("Italian")
                if any(k in desc for k in ["portuguese", "maria", "pt-"]):
                    self._local_languages.add("Portuguese")
        except Exception as e:
            print(f"Error enumerating local SAPI voices: {e}")

    def has_local_voice_for_language(self, lang_code_or_name: str) -> bool:
        """Returns True if the current OS has an offline voice pack for the language."""
        if not lang_code_or_name or lang_code_or_name == "Auto":
            return True
        return lang_code_or_name in self._local_languages

    def detect_language(self, text: str) -> str:
        """Detects language from text characters when language is Auto or unspecified."""
        # 日语假名检测
        if any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in text):
            return "Japanese"
        # 韩语谚文字母检测
        if any('\uac00' <= ch <= '\ud7af' or '\u1100' <= ch <= '\u11ff' for ch in text):
            return "Korean"
        # 俄语西里尔字母检测
        if any('\u0400' <= ch <= '\u04ff' for ch in text):
            return "Russian"
        # 阿拉伯字母检测
        if any('\u0600' <= ch <= '\u06ff' for ch in text):
            return "Arabic"
        # 泰文字母检测
        if any('\u0e00' <= ch <= '\u0e7f' for ch in text):
            return "Thai"
        # 中文汉字检测
        if any('\u4e00' <= ch <= '\u9fff' for ch in text):
            return "Chinese"
        # 默认返回英文
        return "English"

    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self):
        """Immediately halts any in-progress speech."""
        # 1. 停止 Edge TTS 生成工作线程
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            self._current_worker.wait(500)
            self._current_worker = None

        # 2. 停止 QMediaPlayer 播放
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()

        self._cleanup_temp_file()

        # 3. 停止 SAPI 播放
        if sys.platform == "win32" and self._sapi_voice:
            try:
                # SVSFPurgeBeforeSpeak = 2
                self._sapi_voice.Speak("", 2)
            except Exception:
                pass

        # 4. 停止 macOS 原生 say 进程
        if sys.platform == "darwin" and self._mac_process:
            try:
                self._mac_process.terminate()
            except Exception:
                pass
            self._mac_process = None

        if self._poll_timer.isActive():
            self._poll_timer.stop()

        if self._is_speaking:
            self._is_speaking = False
            self.speech_finished.emit()

    def _cleanup_temp_file(self):
        if self._current_temp_file:
            try:
                if os.path.exists(self._current_temp_file):
                    os.remove(self._current_temp_file)
            except Exception:
                pass
            self._current_temp_file = None

    def speak(self, text: str, lang: Optional[str] = None, parent_widget: Optional[QWidget] = None):
        """
        Asynchronously speaks the provided text.
        
        If the language lacks a local Windows voice pack, checks and prompts the user (unless suppressed),
        then invokes Microsoft Edge Neural TTS with SAPI fallback.
        """
        text = text.strip()
        if not text:
            return

        self.stop()

        # 解析实际语种
        if not lang or lang == "Auto":
            resolved_lang = self.detect_language(text)
        else:
            resolved_lang = lang

        # 检测本地离线语音包缺失并友好提醒
        if not self.has_local_voice_for_language(resolved_lang):
            suppressed = settings.get("tts_suppress_missing_voice_dialog", False)
            if not suppressed:
                from ui.components.tts_notice_dialog import TTSNoticeDialog
                from config.languages import get_language_label
                lang_display = get_language_label(resolved_lang).split(" ")[0]
                dialog = TTSNoticeDialog(lang_name=lang_display, parent=parent_widget)
                if dialog.exec() != QDialog.Accepted:
                    # 用户点击取消
                    return

        # 优先使用 Edge Neural TTS
        edge_voice = EDGE_VOICE_MAP.get(resolved_lang, "en-US-JennyNeural")
        self._is_speaking = True
        self.speech_started.emit(text)

        self._current_worker = EdgeTTSWorker(text, edge_voice)
        self._current_worker.finished_signal.connect(self._on_edge_tts_generated)
        self._current_worker.error_signal.connect(lambda err: self._on_edge_tts_error(err, text))
        self._current_worker.start()

    def _on_edge_tts_generated(self, temp_file_path: str):
        """Callback when Edge TTS generates the MP3 audio file."""
        if not self._is_speaking:
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
            return

        self._cleanup_temp_file()
        self._current_temp_file = temp_file_path
        self._player.setSource(QUrl.fromLocalFile(temp_file_path))
        self._player.play()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        """Triggered when audio playback starts, pauses, or finishes."""
        if state == QMediaPlayer.PlaybackState.StoppedState and self._is_speaking:
            self._is_speaking = False
            self._cleanup_temp_file()
            self.speech_finished.emit()

    def _on_edge_tts_error(self, err_msg: str, fallback_text: str):
        """Fallback to native SAPI when Edge TTS fails (e.g. offline)."""
        print(f"Edge TTS synthesis error, attempting SAPI fallback: {err_msg}")
        if sys.platform == "win32" and self._sapi_voice:
            try:
                self._select_sapi_voice_for_text(fallback_text)
                # SVSFlagsAsync = 1, SVSFPurgeBeforeSpeak = 2 -> 1 | 2 = 3
                self._sapi_voice.Speak(fallback_text, 1 | 2)
                self._poll_timer.start()
                return
            except Exception as e:
                self._is_speaking = False
                self.speech_error.emit(f"语音朗读失败: {e}")
                self.speech_finished.emit()
                return

        self._is_speaking = False
        self.speech_error.emit(f"语音生成失败: {err_msg}")
        self.speech_finished.emit()

    def _check_speech_status(self):
        """Polls SAPI status to detect speech completion."""
        if not self._is_speaking:
            self._poll_timer.stop()
            return

        if sys.platform == "win32" and self._sapi_voice:
            try:
                status = self._sapi_voice.Status
                if status.RunningState != 2:
                    self._is_speaking = False
                    self._poll_timer.stop()
                    self.speech_finished.emit()
            except Exception:
                self._is_speaking = False
                self._poll_timer.stop()
                self.speech_finished.emit()
        elif sys.platform == "darwin":
            if self._mac_process and self._mac_process.poll() is not None:
                self._mac_process = None
                self._is_speaking = False
                self._poll_timer.stop()
                self.speech_finished.emit()

    def _select_sapi_voice_for_text(self, text: str):
        """Selects suitable SAPI voice for fallback speaking."""
        if not self._sapi_voice:
            return

        try:
            has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in text)
            voices = self._sapi_voice.GetVoices()
            target_voice = None

            for i in range(voices.Count):
                v = voices.Item(i)
                desc = v.GetDescription().lower()
                if has_cjk and any(k in desc for k in ["chinese", "huihui", "zh", "yaoyao"]):
                    target_voice = v
                    break
                elif not has_cjk and any(k in desc for k in ["english", "zira", "david", "en"]):
                    target_voice = v
                    break

            if target_voice is not None:
                self._sapi_voice.Voice = target_voice
        except Exception:
            pass


tts_manager = TTSManager.get_instance()

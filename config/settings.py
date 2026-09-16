# -*- coding: utf-8 -*-
"""Application settings and persistence."""

import json
import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, List

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

SETTINGS_FILE = _get_base_dir() / "settings.json"

APP_NAME = "Just Translate"
APP_VERSION = "1.0.1"
APP_AUTHOR = "Kutori"
APP_DESCRIPTION = "专为高频语言处理与深度文本打磨打造的现代化桌面 AI 生产力工具"

DEFAULT_PROFILES = [
    {
        "id": "llama_cpp",
        "name": "本地 Hy-MT2 & GLM-OCR (8001)",
        "base_url": "http://127.0.0.1:8001/v1",
        "api_key": "sk-no-key",
        "model": "Hy-MT2-7B",
        "ocr_model": "GLM-OCR"
    },
    {
        "id": "ollama",
        "name": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b"
    },
    {
        "id": "deepseek",
        "name": "DeepSeek API",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat"
    },
    {
        "id": "openai",
        "name": "OpenAI API",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini"
    }
]

DEFAULT_SETTINGS: Dict[str, Any] = {
    "active_profile_id": "llama_cpp",
    "profiles": DEFAULT_PROFILES,
    "temperature": 0.3,
    "timeout_seconds": 30.0,
    "max_retries": 2,
    "auto_detect_language": True,
    "custom_prompts": {
        "translate": "",
        "polish": "",
        "dictionary": ""
    },
    "last_src_lang": "Auto",
    "last_target_lang": "English",
    "last_mode": "translate",
    "window_geometry": {
        "x": -1,
        "y": -1,
        "width": 1050,
        "height": 680,
        "maximized": False
    },
    "minimize_to_tray_on_close": True,
    "enable_system_tray": True,
    "tray_notification_shown": False,
    "ocr_base_url": "http://127.0.0.1:8001/v1",
    "ocr_model": "GLM-OCR",
    "ocr_api_key": "sk-no-key",
    "recent_other_src_langs": ["Korean", "French"],
    "output_format": "markdown",
    "history_limit": 100,
    "eco_mode": False,
    "app_theme": "dark",
    "tts_suppress_missing_voice_dialog": False
}

class AppSettings:
    """Settings manager with disk persistence."""
    def __init__(self, file_path: Path = SETTINGS_FILE):
        self.file_path = file_path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        # 优先检测若目标路径不存在、但 _internal/settings.json 存在时，进行无缝前向迁移
        if not self.file_path.exists():
            legacy_file = self.file_path.parent / "_internal" / "settings.json"
            if legacy_file.exists():
                try:
                    shutil.copy2(legacy_file, self.file_path)
                except Exception:
                    pass

        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data = {**DEFAULT_SETTINGS, **saved}
                    # 确保 profiles 结构正确
                    if "profiles" not in self.data or not self.data["profiles"]:
                        self.data["profiles"] = DEFAULT_PROFILES
                    return
            except Exception:
                pass
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        self.save()

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

    def get_active_profile(self) -> Dict[str, Any]:
        active_id = self.data.get("active_profile_id", "llama_cpp")
        profiles = self.data.get("profiles", [])
        for p in profiles:
            if p.get("id") == active_id:
                return p
        if profiles:
            return profiles[0]
        return DEFAULT_PROFILES[0]

    def set_active_profile_id(self, profile_id: str):
        self.data["active_profile_id"] = profile_id
        self.save()

    def update_profile(self, profile_id: str, updated_fields: Dict[str, Any]):
        for p in self.data.get("profiles", []):
            if p.get("id") == profile_id:
                p.update(updated_fields)
                self.save()
                return

    def add_profile(self, profile: Dict[str, Any]):
        self.data.setdefault("profiles", []).append(profile)
        self.save()

    def delete_profile(self, profile_id: str):
        profiles = [p for p in self.data.get("profiles", []) if p.get("id") != profile_id]
        if profiles:
            self.data["profiles"] = profiles
            if self.data.get("active_profile_id") == profile_id:
                self.data["active_profile_id"] = profiles[0]["id"]
            self.save()

    def get_recent_other_langs(self, is_src: bool) -> List[str]:
        key = "recent_other_src_langs" if is_src else "recent_other_target_langs"
        recent = self.data.get(key, ["Korean", "French"])
        if not isinstance(recent, list) or len(recent) < 2:
            return ["Korean", "French"]
        return recent[:2]

    def add_recent_other_lang(self, is_src: bool, lang_code: str):
        if not lang_code or lang_code in ("Auto", "Chinese", "English", "Japanese"):
            return
        key = "recent_other_src_langs" if is_src else "recent_other_target_langs"
        recent = self.get_recent_other_langs(is_src)
        new_recent = [lang_code] + [x for x in recent if x != lang_code]
        self.data[key] = new_recent[:2]
        self.save()

# Global singleton
settings = AppSettings()

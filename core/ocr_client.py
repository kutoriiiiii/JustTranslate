# -*- coding: utf-8 -*-
"""OCR client supporting vision-based models such as GLM-OCR with 30s timeout and retry."""

import base64
import io
import time
from pathlib import Path
from typing import Optional, Union, Tuple, Dict, Any
import httpx
from PIL import Image

# Known vision and multimodal model identifier patterns
_VISION_KEYWORDS = (
    "vl", "vision", "ocr", "omni", "llava", "internvl", "minicpm-v",
    "pixtral", "gemini", "claude-3", "gpt-4o", "gpt-4-turbo", "paligemma",
    "4v", "vlm", "cogvlm"
)

# Known pure text model patterns (explicitly non-vision unless specified with VL)
_KNOWN_TEXT_MODELS = (
    "deepseek-chat", "deepseek-coder", "deepseek-reasoner",
    "qwen2.5-7b", "qwen2.5-14b", "qwen2.5-32b", "qwen2.5-72b",
    "qwen-turbo", "qwen-plus", "qwen-max",
    "hy-mt2", "llama-2", "llama-3-8b", "llama-3-70b", "llama-3.1-8b", "llama-3.1-70b"
)

def is_vision_model(model_name: str) -> bool:
    """Detects whether a model name possesses multimodal vision/OCR capabilities."""
    if not model_name:
        return False
    lower = model_name.lower().strip()
    
    # 1. Exact match / prefix check against known vision models
    if any(k in lower for k in _VISION_KEYWORDS):
        return True
        
    # 2. Check endings like "-v" or "_v" or "4v" (e.g. "model-v" or "glm-4v")
    if lower.endswith(("-v", "_v", "4v")):
        return True
        
    return False

def check_ocr_capability(profile: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[str], Optional[str], Optional[str]]:
    """Evaluates whether the given profile or environment has valid OCR capability.
    
    Returns:
        (has_ocr, message, effective_base_url, effective_api_key, effective_model)
    """
    model_name = profile.get("model", "").strip()
    profile_ocr_model = profile.get("ocr_model", "").strip()
    profile_base_url = profile.get("base_url", "").strip()
    profile_api_key = profile.get("api_key", "").strip()
    
    # Case 1: Profile has explicitly configured an OCR model
    if profile_ocr_model:
        return (
            True,
            f"已配置专用 OCR 模型 [{profile_ocr_model}]",
            profile_base_url,
            profile_api_key,
            profile_ocr_model
        )
        
    # Case 2: Main profile model is a known vision model (e.g. gpt-4o, gpt-4o-mini, qwen-vl)
    if is_vision_model(model_name):
        return (
            True,
            f"主模型具备多模态视觉能力 [{model_name}]",
            profile_base_url,
            profile_api_key,
            model_name
        )
        
    # Case 3: Profile is llama_cpp pointing to local server where GLM-OCR is on 8001
    if profile.get("id") == "llama_cpp" and "8001" in profile_base_url:
        return (
            True,
            "本地 GLM-OCR (8001)",
            profile_base_url,
            profile_api_key,
            "GLM-OCR"
        )
        
    # Case 4: Profile is a pure text model and no profile-level OCR model is set
    return (
        False,
        f"当前配置的模型【{model_name or '未命名'}】为纯文本模型，不具备 OCR 识图功能。",
        None,
        None,
        None
    )


class OCRClient:
    """Client for calling multimodal vision OCR endpoints (e.g. GLM-OCR, GPT-4o, Qwen-VL)."""

    def __init__(self, base_url: str, api_key: str = "", model: str = "GLM-OCR", timeout: float = 30.0, max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "sk-no-key-required"
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    def _get_endpoint(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        elif self.base_url.endswith("/chat/completions"):
            return self.base_url
        else:
            return f"{self.base_url}/v1/chat/completions"

    @staticmethod
    def prepare_image_base64(image_input: Union[bytes, str, Path, Image.Image], max_dimension: int = 2048) -> str:
        """Converts diverse image sources into standard base64 data url, with safe resolution limits."""
        if isinstance(image_input, Image.Image):
            img = image_input.copy()
        elif isinstance(image_input, (str, Path)):
            img = Image.open(str(image_input))
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        # 转换为 RGB 模式（针对 RGBA 或 P 模式进行兼容处理）
        if img.mode in ("RGBA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 智能等比例缩放（防止巨幅图片超内存，同时保持清晰度）
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"

    def recognize_text(
        self, 
        image_input: Union[bytes, str, Path, Image.Image], 
        prompt_text: str = "识别图片中的所有文字",
        controller: Optional[Any] = None
    ) -> str:
        """Sends multimodal request to OCR model and returns extracted text with 30s timeout, proxy bypass, and retry."""
        from .network_utils import create_httpx_client

        data_url = self.prepare_image_base64(image_input)
        url = self._get_endpoint()
        headers = self._get_headers()

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "max_tokens": 2048,
            "stream": False
        }

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            if controller and getattr(controller, "is_aborted", False):
                return ""

            attempt += 1
            try:
                client = create_httpx_client(url, timeout=httpx.Timeout(self.timeout, connect=10.0))
                if controller and hasattr(controller, "active_client"):
                    controller.active_client = client

                with client:
                    resp = client.post(url, json=payload, headers=headers)
                    if controller and getattr(controller, "is_aborted", False):
                        return ""

                    if resp.status_code != 200:
                        err_text = resp.text[:200]
                        # 专门捕获模型不支持视觉/图片的报错信息
                        lower_err = err_text.lower()
                        if resp.status_code in (400, 404, 422) and any(kw in lower_err for kw in ("image", "vision", "multimodal", "unsupported", "content")):
                            raise ValueError(f"当前模型【{self.model}】不支持图片识别输入（远程接口提示：{err_text}）。请在设置中切换为具备视觉功能的多模态模型（如 GPT-4o、Qwen-VL 等）。")
                        raise RuntimeError(f"OCR 服务返回错误 HTTP {resp.status_code}: {err_text}")

                    result_json = resp.json()
                    choices = result_json.get("choices", [])
                    if not choices:
                        return ""
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    return content.strip()

            except ValueError:
                # 明确的模型能力不匹配，立即抛出，不再重试
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, RuntimeError) as e:
                if controller and getattr(controller, "is_aborted", False):
                    return ""
                last_error = e
                if attempt <= self.max_retries:
                    time.sleep(1.0)
                    continue
                else:
                    break
            except Exception as e:
                if controller and getattr(controller, "is_aborted", False):
                    return ""
                last_error = e
                break

        if controller and getattr(controller, "is_aborted", False):
            return ""

        if isinstance(last_error, httpx.TimeoutException):
            raise TimeoutError(f"OCR 请求在 30 秒内未能响应或连接超时（已重试 {attempt-1} 次）。")
        raise RuntimeError(f"OCR 识别失败: {str(last_error)}")

# -*- coding: utf-8 -*-
"""Ollama Native / OpenAI-compatible Adapter.

Rules:
- Targets local Ollama instance (typically http://127.0.0.1:11434).
- Most thinking models support think: true/false.
- GPT-OSS models use think: "low"/"medium"/"high" and cannot be completely turned off.
- Stream parses message.thinking (or delta.reasoning_content).
- Strips and cleanly handles any leaked <think>...</think> boundary tags.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class OllamaAdapter(ProviderAdapter):
    """Adapter for Ollama."""

    protocol_name = "ollama_native"

    def __init__(self, provider: str = "ollama", model: str = ""):
        super().__init__(provider=provider, model=model)
        self._in_think_tag = False

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/api/chat") or base.endswith("/chat/completions"):
            return base
        # Default to OpenAI compatible endpoint on 11434/v1 or native /api/chat
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/api/chat"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip() and api_key != "sk-no-key":
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

    def _is_gpt_oss(self, model: str) -> bool:
        return "gpt-oss" in model.lower()

    def _is_known_thinking_model(self, model: str) -> bool:
        lower = model.lower()
        return any(k in lower for k in ("qwen3", "deepseek-r1", "deepseek-v3.1", "thinking", "reasoner"))

    def build_payload(
        self,
        model: str,
        messages: List[Dict[str, str]],
        reasoning_intent: str,  # "off", "on", "auto"
        effort_level: str = "medium",
        budget_tokens: Optional[int] = None,
        temperature: float = 0.3,
        stream: bool = True,
        max_tokens: Optional[int] = None,
        strip_reasoning_param: bool = False
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        is_gpt_oss = self._is_gpt_oss(model)
        is_known_thinking = self._is_known_thinking_model(model)

        if not strip_reasoning_param:
            if is_gpt_oss:
                # GPT-OSS only supports effort levels
                valid_eff = effort_level.lower() if effort_level.lower() in ("low", "medium", "high") else "low"
                payload["think"] = valid_eff
            elif is_known_thinking:
                if reasoning_intent == "off":
                    payload["think"] = False
                elif reasoning_intent == "on":
                    payload["think"] = True
            elif reasoning_intent == "on":
                # Unknown model where user explicitly requested on
                payload["think"] = True

        return payload

    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        line_str = line.strip()
        if not line_str:
            return None

        # May be raw JSON line or data: SSE line
        if line_str.startswith("data:"):
            line_str = line_str[5:].strip()
            if line_str == "[DONE]":
                return ParsedChunk(is_done=True)

        try:
            chunk = json.loads(line_str)
        except json.JSONDecodeError:
            return None

        # Check Ollama done flag
        if chunk.get("done", False):
            return ParsedChunk(is_done=True, raw_event=chunk)

        content = ""
        reasoning = ""

        # Format 1: Ollama native (/api/chat)
        if "message" in chunk:
            msg = chunk["message"]
            content = msg.get("content", "") or ""
            reasoning = msg.get("thinking", "") or ""
        # Format 2: Ollama /v1/chat/completions
        elif "choices" in chunk:
            delta = chunk["choices"][0].get("delta", {}) if chunk["choices"] else {}
            content = delta.get("content", "") or ""
            reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "") or ""

        # Handle inline <think> tags if model outputs tags into content
        if "<think>" in content:
            self._in_think_tag = True
            parts = content.split("<think>", 1)
            content = parts[0]
            if "</think>" in parts[1]:
                subparts = parts[1].split("</think>", 1)
                reasoning += subparts[0]
                content += subparts[1]
                self._in_think_tag = False
            else:
                reasoning += parts[1]
        elif "</think>" in content:
            parts = content.split("</think>", 1)
            reasoning += parts[0]
            content = parts[1]
            self._in_think_tag = False
        elif self._in_think_tag:
            reasoning += content
            content = ""

        return ParsedChunk(content=content, reasoning=reasoning, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="Ollama 认证错误。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="Ollama 模型未在本地拉取或不存在。")

        if status_code == 400:
            if "think" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="think",
                    category="reasoning_param",
                    message="Ollama 模型不接受 think 参数。",
                    can_retry_without_reasoning=True
                )

        return ReasoningErrorClassification(
            is_reasoning_parameter_error=False,
            category="client_error" if status_code < 500 else "server_error",
            message=f"HTTP {status_code}: {response_body[:200]}"
        )

    def probe(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 15.0
    ) -> ProbeResult:
        url = self.get_endpoint_url(base_url)
        headers = self.get_headers(api_key)

        is_gpt_oss = self._is_gpt_oss(model)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "stream": False
        }
        if is_gpt_oss:
            payload["think"] = "low"
        else:
            payload["think"] = False

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    state = ProbeState.FORCED_ON if is_gpt_oss else ProbeState.CONFIRMED_SUPPORTED
                    details = "Ollama GPT-OSS 仅支持调节思考强度，无法完全关闭。" if is_gpt_oss else "Ollama 已确认支持通过 think: false 关闭思考 (HTTP 200)。"
                    return ProbeResult(
                        state=state,
                        control_kind=ControlKind.BOOLEAN if not is_gpt_oss else ControlKind.EFFORT_ENUM,
                        details=details,
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"Ollama 拒绝 think 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

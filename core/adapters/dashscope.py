# -*- coding: utf-8 -*-
"""Alibaba Cloud DashScope / Qwen Adapter.

Rules:
- Targets dashscope.aliyuncs.com/compatible-mode/v1.
- Reasoning models (qwq, qwen3.8, qwen-max) support enable_thinking: true/false.
- Also supports thinking_budget integer.
- Stream parses delta.reasoning_content.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class DashScopeAdapter(ProviderAdapter):
    """Adapter for Alibaba DashScope OpenAI-compatible endpoint."""

    protocol_name = "dashscope"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/chat/completions"
        return f"{base}/compatible-mode/v1/chat/completions" if "dashscope" in base and "compatible-mode" not in base else f"{base}/v1/chat/completions"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

    def _is_thinking_model(self, model: str) -> bool:
        lower = model.lower()
        return any(k in lower for k in ("qwq", "qwen3.8", "qwen-max-latest", "thinking"))

    def _is_qwen38(self, model: str) -> bool:
        return "qwen3.8" in model.lower()

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
            "temperature": temperature,
            "stream": stream
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        is_thinking = self._is_thinking_model(model)
        is_q38 = self._is_qwen38(model)

        if is_thinking and not strip_reasoning_param:
            if is_q38:
                # Qwen3.8 supports reasoning_effort ('none','low','medium','xhigh')
                # Constraint: reasoning_effort and thinking_budget MUST NOT be set simultaneously
                if reasoning_intent == "off":
                    payload["reasoning_effort"] = "none"
                elif reasoning_intent == "on":
                    if budget_tokens and budget_tokens > 0:
                        # If budget specified, use enable_thinking + thinking_budget without reasoning_effort
                        payload["enable_thinking"] = True
                        payload["thinking_budget"] = budget_tokens
                    else:
                        eff_map = {"low": "low", "medium": "medium", "high": "xhigh", "max": "xhigh"}
                        payload["reasoning_effort"] = eff_map.get(effort_level.lower(), "medium")
            else:
                if reasoning_intent == "off":
                    payload["enable_thinking"] = False
                elif reasoning_intent == "on":
                    payload["enable_thinking"] = True
                    if budget_tokens and budget_tokens > 0:
                        payload["thinking_budget"] = budget_tokens

        return payload

    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        line_str = line.strip()
        if not line_str.startswith("data:"):
            return None
        data_str = line_str[5:].strip()
        if data_str == "[DONE]":
            return ParsedChunk(is_done=True)

        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        content = ""
        reasoning = ""
        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            reasoning = delta.get("reasoning_content", "") or ""

        return ParsedChunk(content=content, reasoning=reasoning, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="百炼 API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="百炼模型未找到。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="百炼调用额度超限。")

        if status_code == 400:
            if "enable_thinking" in lower_body or "thinking_budget" in lower_body or "thinking" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="enable_thinking",
                    category="reasoning_param",
                    message="该模型不支持 enable_thinking 参数。",
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

        is_thinking = self._is_thinking_model(model)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "stream": False
        }
        if is_thinking:
            payload["enable_thinking"] = False

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return ProbeResult(
                        state=ProbeState.CONFIRMED_SUPPORTED if is_thinking else ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.BOOLEAN,
                        details="百炼端点已确认支持 enable_thinking 开关 (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"百炼拒绝 enable_thinking: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

# -*- coding: utf-8 -*-
"""DeepSeek Official API Adapter.

Rules:
- Targets api.deepseek.com Chat Completions.
- Reasoning models (deepseek-reasoner, deepseek-r1) support disabling thinking via
  extra_body: {"thinking": {"type": "disabled"}}.
- Reasoning output streamed in choices[0].delta.reasoning_content.
- Temperature & penalty adjustments are not recommended while thinking is on.
- Non-reasoning models (deepseek-chat) do not take thinking parameters.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class DeepSeekAdapter(ProviderAdapter):
    """Adapter for DeepSeek API."""

    protocol_name = "deepseek"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

    def _is_reasoning_model(self, model: str) -> bool:
        lower = model.lower().strip()
        return any(k in lower for k in ("reasoner", "-r1", "thinking", "deepseek-v4", "deepseek-flash"))

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
            "stream": stream
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        is_reasoner = self._is_reasoning_model(model)

        if is_reasoner and not strip_reasoning_param:
            if reasoning_intent == "off":
                # Explicitly disable thinking
                payload["thinking"] = {"type": "disabled"}
                payload["temperature"] = temperature
            elif reasoning_intent == "on":
                payload["thinking"] = {"type": "enabled"}
                # DeepSeek official constraint: top_p minimum 0.95 when thinking
                payload["top_p"] = 0.95
                payload["temperature"] = 1.0
            else:
                # auto: let default rule apply
                payload["temperature"] = 1.0
        else:
            payload["temperature"] = temperature

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
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="DeepSeek API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="DeepSeek 模型不存在。")
        if status_code == 429 or "insufficient_quota" in lower_body or "balance" in lower_body:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="DeepSeek 账户余额不足或并发受限。")

        if status_code == 400:
            if "thinking" in lower_body or "reasoning" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="thinking",
                    category="reasoning_param",
                    message="DeepSeek 模型不接受 thinking 参数。",
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

        is_reasoner = self._is_reasoning_model(model)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "stream": False
        }
        if is_reasoner:
            payload["thinking"] = {"type": "disabled"}

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    reasoning_content = choices[0].get("message", {}).get("reasoning_content", "") if choices else ""
                    if is_reasoner and not reasoning_content:
                        return ProbeResult(
                            state=ProbeState.CONFIRMED_SUPPORTED,
                            control_kind=ControlKind.THINKING_OBJECT,
                            details="已确认支持通过 thinking: {type: disabled} 关闭思考（模型成功跳过思维链直接秒回）。",
                            raw_status_code=200
                        )
                    return ProbeResult(
                        state=ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.THINKING_OBJECT if is_reasoner else ControlKind.NONE,
                        details="请求成功 (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"DeepSeek 服务端拒绝 thinking 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

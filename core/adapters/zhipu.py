# -*- coding: utf-8 -*-
"""Zhipu AI (BigModel / Z.AI) Adapter.

Rules:
- Targets open.bigmodel.cn Chat Completions.
- Flexible models (GLM-4.5, GLM-5.2) support thinking: {"type": "disabled"/"enabled"}.
- Pure reasoning models (GLM-Zero, GLM-5.3, GLM-4.7) are FORCED THINKING; passing "disabled" returns 400.
- Stream parses delta.reasoning_content and safely isolates any <think> tags.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class ZhipuAdapter(ProviderAdapter):
    """Adapter for Zhipu AI / Z.AI."""

    protocol_name = "zhipu"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/chat/completions"
        return f"{base}/api/paas/v4/chat/completions" if "bigmodel.cn" in base else f"{base}/v1/chat/completions"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

    def _is_forced_thinking_model(self, model: str) -> bool:
        lower = model.lower()
        return any(k in lower for k in ("glm-5.3", "glm-zero"))

    def _is_flexible_thinking_model(self, model: str) -> bool:
        lower = model.lower()
        return any(k in lower for k in ("glm-4.5", "glm-4.6", "glm-4.7", "glm-5.1", "glm-5.2", "glm-5"))

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

        is_forced = self._is_forced_thinking_model(model)
        is_flex = self._is_flexible_thinking_model(model)
        is_53 = "glm-5.3" in model.lower()

        if not strip_reasoning_param:
            if is_53:
                # GLM-5.3 / GLM-5.3-Flash: thinking is forced ON; accepts reasoning_effort ('low','high','max')
                payload["thinking"] = {"type": "enabled"}
                if reasoning_intent == "off":
                    # When user wants off, set reasoning_effort to lowest possible tier 'low' to minimize latency
                    payload["reasoning_effort"] = "low"
                elif reasoning_intent == "on":
                    valid_eff = effort_level.lower() if effort_level.lower() in ("low", "high", "max") else "max"
                    payload["reasoning_effort"] = valid_eff
                else:
                    payload["reasoning_effort"] = "max"
                payload["temperature"] = 1.0
                payload["top_p"] = 0.95
            elif is_flex and not is_forced:
                if reasoning_intent == "off":
                    payload["thinking"] = {"type": "disabled"}
                elif reasoning_intent == "on":
                    payload["thinking"] = {"type": "enabled"}
            elif is_forced:
                # Other forced models (e.g. GLM-Zero) cannot disable; if intent is on, specify enabled
                if reasoning_intent == "on":
                    payload["thinking"] = {"type": "enabled"}
                # If off, we do NOT send type: disabled because it errors 400!

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
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="智谱 API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="智谱模型未找到。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="智谱调用额度超限。")

        if status_code == 400:
            if "thinking" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="thinking",
                    category="reasoning_param",
                    message="智谱模型拒绝当前 thinking 参数（部分模型为强制思考）。",
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

        is_forced = self._is_forced_thinking_model(model)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "stream": False
        }
        if not is_forced:
            payload["thinking"] = {"type": "disabled"}

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    state = ProbeState.FORCED_ON if is_forced else ProbeState.CONFIRMED_SUPPORTED
                    details = "智谱模型为强制思考模型，不可关闭思考。" if is_forced else "智谱模型已确认支持 thinking: {type: disabled} 关闭思考。"
                    return ProbeResult(
                        state=state,
                        control_kind=ControlKind.THINKING_OBJECT,
                        details=details,
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"智谱拒绝 thinking 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

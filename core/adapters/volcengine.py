# -*- coding: utf-8 -*-
"""Volcengine Ark (火山引擎方舟) Adapter.

Rules:
- Targets ark.cn-beijing.volces.com/api/v3/chat/completions.
- Uses reasoning_effort: "none", "minimal", "low", "high".
- Supports disabling thinking via "none" or "minimal".
- Top-p is clamped to >= 0.95 when thinking is enabled.
- Stream parses delta.reasoning_content.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class VolcengineAdapter(ProviderAdapter):
    """Adapter for Volcengine Ark platform."""

    protocol_name = "volcengine"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/chat/completions"
        return f"{base}/api/v3/chat/completions" if "volces.com" in base else f"{base}/v1/chat/completions"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

    def _is_known_reasoning_model(self, model: str) -> bool:
        lower = model.lower()
        return any(k in lower for k in ("doubao-1.5-pro", "doubao-seed", "doubao-pro", "deepseek"))

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

        is_known = self._is_known_reasoning_model(model)

        if not strip_reasoning_param and is_known:
            if reasoning_intent == "off":
                payload["reasoning_effort"] = "none"
                payload["temperature"] = temperature
            elif reasoning_intent == "on":
                valid_eff = effort_level.lower() if effort_level.lower() in ("low", "high") else "low"
                payload["reasoning_effort"] = valid_eff
                # top_p constraint when thinking
                payload["top_p"] = 0.95
            else:
                payload["temperature"] = temperature
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
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="火山引擎 API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="火山引擎接入点或模型不存在。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="火山引擎调用并发或额度超限。")

        if status_code == 400:
            if "reasoning_effort" in lower_body or "reasoning" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="reasoning_effort",
                    category="reasoning_param",
                    message="火山引擎模型不接受 reasoning_effort 参数。",
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
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "reasoning_effort": "none",
            "stream": False
        }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return ProbeResult(
                        state=ProbeState.CONFIRMED_SUPPORTED,
                        control_kind=ControlKind.EFFORT_ENUM,
                        details="火山引擎接入点已确认支持 reasoning_effort: none 关闭思考 (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"火山引擎拒绝 reasoning_effort: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

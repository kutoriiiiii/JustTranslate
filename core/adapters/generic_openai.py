# -*- coding: utf-8 -*-
"""Generic OpenAI-compatible Adapter.

CRITICAL HARD RULE:
- Unknown endpoints/models DEFAULT to NOT injecting ANY non-standard thinking parameters.
- Model name keywords (e.g. "qwq", "r1") serve ONLY as capability hints; they NEVER dictate API parameters.
- Non-standard parameters are injected ONLY if the user explicitly configured an override
  or an on-demand probe previously confirmed capability at this endpoint.
- Separates delta.reasoning_content from delta.content.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import CapabilityRegistry, ControlKind, ProbeState
from core.network_utils import create_httpx_client


class GenericOpenAIAdapter(ProviderAdapter):
    """Adapter for Generic / Unknown OpenAI-compatible endpoints."""

    protocol_name = "generic_openai"

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
        if api_key and api_key.strip() and api_key != "sk-no-key-required":
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        return headers

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

        # HARD RULE: By default, DO NOT inject any non-standard thinking parameter!
        # Unless strip_reasoning_param is False AND endpoint probe cache or user override explicitly authorizes it
        # (handshake handled via parameters or caller profile override)
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
            # Safely capture reasoning_content if returned by proxy
            reasoning = delta.get("reasoning_content", "") or delta.get("reasoning", "") or ""

        return ParsedChunk(content=content, reasoning=reasoning, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="认证失败，请检查 API Key。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="模型或服务端点不存在 (HTTP 404)。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="超出调用频率或额度限制 (HTTP 429)。")

        if status_code == 400:
            if any(k in lower_body for k in ("reasoning_effort", "thinking", "enable_thinking", "chat_template_kwargs")):
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    category="reasoning_param",
                    message="目标服务端拒绝非标准思考参数。",
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
            "stream": False
        }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    has_reasoning = False
                    if choices:
                        msg = choices[0].get("message", {})
                        has_reasoning = bool(msg.get("reasoning_content") or msg.get("reasoning"))

                    state = ProbeState.CONFIRMED_SUPPORTED if has_reasoning else ProbeState.ACCEPTED_BUT_UNVERIFIED
                    details = "检测到服务商返回了结构化思维链字段。" if has_reasoning else "通用端点连通成功 (HTTP 200)，未检测到非标准思维链，按标准文本模式运行。"
                    return ProbeResult(
                        state=state,
                        control_kind=ControlKind.NONE,
                        details=details,
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

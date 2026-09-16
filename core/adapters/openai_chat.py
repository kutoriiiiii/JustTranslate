# -*- coding: utf-8 -*-
"""OpenAI Chat Completions Adapter.

Rules:
- Used for OpenAI Chat Completions API (/v1/chat/completions).
- o-series (o1, o3, o4) CANNOT disable thinking via reasoning_effort (none is rejected).
  Requires temperature=1.0 and does not accept penalty parameters.
- Non-reasoning models (gpt-4o, gpt-4o-mini, gpt-4.5) MUST NOT be sent reasoning_effort.
- Classifies errors: only marks is_reasoning_parameter_error=True when error explicitly
  mentions reasoning_effort or reasoning parameters.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class OpenAIChatAdapter(ProviderAdapter):
    """Adapter for OpenAI Chat Completions endpoint."""

    protocol_name = "openai_chat"

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

    def _is_o_series(self, model: str) -> bool:
        lower = model.lower().strip()
        return any(lower.startswith(prefix) for prefix in ("o1", "o3", "o4")) and not any(k in lower for k in ("gpt-4o", "audio"))

    def _is_gpt56_series(self, model: str) -> bool:
        lower = model.lower().strip()
        return "gpt-5.6" in lower or any(k in lower for k in ("sol", "terra", "luna"))

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

        is_o = self._is_o_series(model)
        is_56 = self._is_gpt56_series(model)

        if is_56:
            # GPT-5.6 on Chat Completions: supports reasoning_effort ('none','low','medium','high','xhigh','max')
            if not strip_reasoning_param:
                if reasoning_intent == "off":
                    payload["reasoning_effort"] = "none"
                elif reasoning_intent == "on":
                    valid_effort = effort_level.lower() if effort_level.lower() in ("none", "low", "medium", "high", "xhigh", "max") else "medium"
                    payload["reasoning_effort"] = valid_effort
            payload["temperature"] = temperature
            if max_tokens:
                payload["max_tokens"] = max_tokens
        elif is_o:
            # o-series models on chat completions:
            # Temperature is not supported (or fixed 1.0); penalty params unsupported
            # Thinking CANNOT be disabled on Chat Completions
            if not strip_reasoning_param:
                # Map effort level: low, medium, high
                valid_effort = effort_level.lower() if effort_level.lower() in ("low", "medium", "high") else "medium"
                payload["reasoning_effort"] = valid_effort
            # Do NOT add temperature for o-series
            if max_tokens:
                payload["max_completion_tokens"] = max_tokens
        else:
            # Standard chat models (gpt-4o, gpt-4.5, etc.)
            # DO NOT inject reasoning_effort (will trigger 400)
            payload["temperature"] = temperature
            if max_tokens:
                payload["max_tokens"] = max_tokens

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
        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""

        return ParsedChunk(content=content, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        # Check authentication / quota / not found first
        if status_code in (401, 403):
            return ReasoningErrorClassification(
                is_reasoning_parameter_error=False,
                category="auth",
                message="API 认证失败，请检查 API Key 是否正确。"
            )
        if status_code == 404:
            return ReasoningErrorClassification(
                is_reasoning_parameter_error=False,
                category="not_found",
                message="指定的模型或端点不存在 (HTTP 404)。"
            )
        if status_code == 429:
            return ReasoningErrorClassification(
                is_reasoning_parameter_error=False,
                category="quota",
                message="请求超出频率限制或账户额度耗尽 (HTTP 429)。"
            )
        if "context_length_exceeded" in lower_body or "maximum context length" in lower_body:
            return ReasoningErrorClassification(
                is_reasoning_parameter_error=False,
                category="context_length",
                message="文本超出模型最大上下文长度限制。"
            )

        # Explicit check for reasoning parameter 400 error
        if status_code == 400:
            reasoning_keywords = ("reasoning_effort", "reasoning", "unrecognized request argument")
            if any(k in lower_body for k in ("reasoning_effort", "reasoning")):
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="reasoning_effort",
                    category="reasoning_param",
                    message="模型不接受 reasoning_effort 思考参数。",
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

        is_o = self._is_o_series(model)
        if not is_o:
            return ProbeResult(
                state=ProbeState.UNSUPPORTED,
                control_kind=ControlKind.NONE,
                details=f"模型 [{model}] 属于标准对话模型，官方 Chat Completions 不支持 reasoning_effort 参数。"
            )

        # Probe o-series with valid minimal payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "1+1="}],
            "reasoning_effort": "low",
            "stream": False
        }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                    if reasoning_tokens > 0:
                        return ProbeResult(
                            state=ProbeState.CONFIRMED_SUPPORTED,
                            control_kind=ControlKind.EFFORT_ENUM,
                            details=f"已确认支持思考推理（已验证消耗 {reasoning_tokens} reasoning tokens，仅支持 low/medium/high，无法彻底关闭）。",
                            raw_status_code=200
                        )
                    return ProbeResult(
                        state=ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.EFFORT_ENUM,
                        details="参数已被服务端接受 (HTTP 200)，但未返回明确的 reasoning token 证据。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"服务端明确拒绝 reasoning_effort 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    elif classification.category in ("auth", "quota", "not_found"):
                        return ProbeResult(
                            state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA,
                            details=classification.message,
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNSUPPORTED,
                        details=f"探测失败 (HTTP {resp.status_code}): {resp.text[:120]}",
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(
                state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA,
                details=f"网络异常无法建立连接: {str(e)}"
            )

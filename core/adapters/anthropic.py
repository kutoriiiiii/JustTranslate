# -*- coding: utf-8 -*-
"""Anthropic Messages API Adapter.

Rules:
- Targets Anthropic Messages API (/v1/messages).
- Adaptive thinking: thinking: {"type": "adaptive"} with output_config.effort for newer models.
- Manual thinking: thinking: {"type": "enabled", "budget_tokens": N} for models requiring budget.
  Budget must be >= 1024, and max_tokens must be > budget_tokens.
- Disabling thinking: completely OMIT the thinking block.
- Constraint: temperature MUST be 1.0 when thinking is enabled; omitted top_k.
- Stream: parses thinking_delta vs text_delta without concatenating CoT into content.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic Messages API."""

    protocol_name = "anthropic_messages"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/messages"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/messages"
        return f"{base}/v1/messages"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "anthropic-version": "2023-06-01"
        }
        if api_key and api_key.strip():
            headers["x-api-key"] = api_key.strip()
        return headers

    def _is_claude5_requires_disabled_type(self, model: str) -> bool:
        lower = model.lower()
        return "claude-sonnet-5" in lower or "claude-opus-5" in lower

    def _is_claude5_forced_on(self, model: str) -> bool:
        lower = model.lower()
        return "claude-fable-5" in lower or "claude-mythos-5" in lower

    def _is_adaptive_model(self, model: str) -> bool:
        lower = model.lower()
        # Claude 4.6, 4.7, 4.8, 5+ use adaptive thinking
        return any(k in lower for k in ("claude-4.6", "claude-4.7", "claude-4.8", "claude-opus-4", "claude-sonnet-4", "claude-5", "claude-sonnet-5", "claude-opus-5", "claude-fable-5", "claude-mythos-5"))

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
        # Convert messages if system prompt is in messages
        system_prompt = ""
        anthropic_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_prompt += content + "\n"
            else:
                anthropic_messages.append({"role": role, "content": content})

        # Anthropic requires max_tokens to be set
        effective_max_tokens = max_tokens or 4096

        payload: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "stream": stream,
            "max_tokens": effective_max_tokens
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        is_claude5_disabled = self._is_claude5_requires_disabled_type(model)
        is_adaptive = self._is_adaptive_model(model)
        enable_thinking = (reasoning_intent == "on") and not strip_reasoning_param

        if enable_thinking:
            # Temperature MUST be 1.0 when thinking is enabled on Claude
            payload["temperature"] = 1.0

            if is_adaptive:
                valid_effort = effort_level.lower() if effort_level.lower() in ("low", "medium", "high", "max") else "medium"
                payload["thinking"] = {"type": "adaptive"}
                payload["output_config"] = {"effort": valid_effort}
            else:
                # Manual budget thinking (legacy 3.5 only; 4.7+ forbids budget_tokens)
                budget = max(1024, int(budget_tokens or 1024))
                if payload["max_tokens"] <= budget:
                    payload["max_tokens"] = budget + 2048
                payload["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget
                }
        else:
            # Disabling thinking
            payload["temperature"] = temperature
            if not strip_reasoning_param and is_claude5_disabled and reasoning_intent == "off":
                # Claude Sonnet 5 and Opus 5 defaults thinking ON; requires thinking: {"type": "disabled"}
                payload["thinking"] = {"type": "disabled"}
            # For Claude 4.6 / 4.7+, simply omit thinking completely to disable

        return payload

    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        line_str = line.strip()
        if not line_str.startswith("data:"):
            return None
        data_str = line_str[5:].strip()

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        event_type = event.get("type", "")

        if event_type == "message_stop":
            return ParsedChunk(is_done=True, raw_event=event)

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")
            if delta_type == "thinking_delta":
                # Thinking trace stream
                return ParsedChunk(reasoning=delta.get("thinking", ""), raw_event=event)
            elif delta_type == "text_delta":
                # Final translation stream
                return ParsedChunk(content=delta.get("text", ""), raw_event=event)

        return None

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="Anthropic API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="Anthropic 模型不存在或已退役。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="Anthropic 额度或并发频率超限。")

        if status_code == 400:
            if any(k in lower_body for k in ("thinking", "budget_tokens", "adaptive", "output_config")):
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="thinking",
                    category="reasoning_param",
                    message="Anthropic 模型不接受当前 thinking 参数配置。",
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

        # Probe with adaptive or manual budget with compliant max_tokens
        if self._is_adaptive_model(model):
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "1+1="}],
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"},
                "max_tokens": 1024,
                "temperature": 1.0,
                "stream": False
            }
        else:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "1+1="}],
                "thinking": {"type": "enabled", "budget_tokens": 1024},
                "max_tokens": 2048,
                "temperature": 1.0,
                "stream": False
            }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content_blocks = data.get("content", [])
                    has_thinking = any(b.get("type") in ("thinking", "redacted_thinking") for b in content_blocks)
                    if has_thinking:
                        return ProbeResult(
                            state=ProbeState.CONFIRMED_SUPPORTED,
                            control_kind=ControlKind.ADAPTIVE_EFFORT if self._is_adaptive_model(model) else ControlKind.TOKEN_BUDGET,
                            details="已确认支持 Anthropic 思考模式（已成功解析 thinking content block，省略该参数即可彻底关闭）。",
                            raw_status_code=200
                        )
                    return ProbeResult(
                        state=ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.TOKEN_BUDGET,
                        details="请求成功 (HTTP 200)，但未在输出中检索到 thinking block。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"Anthropic 服务端拒绝 thinking 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

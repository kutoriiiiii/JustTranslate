# -*- coding: utf-8 -*-
"""OpenAI Responses API Adapter.

Rules:
- Targets OpenAI Responses API (/v1/responses).
- Uses reasoning.effort: "none", "minimal", "low", "medium", "high", "xhigh".
- Supports disabling thinking with "none" on GPT-5.1+ models.
- Parses response events separating reasoning output items from text content parts.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class OpenAIResponsesAdapter(ProviderAdapter):
    """Adapter for OpenAI Responses API."""

    protocol_name = "openai_responses"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/responses"):
            return base
        if re.search(r'/v\d+$', base, re.IGNORECASE):
            return f"{base}/responses"
        return f"{base}/v1/responses"

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
        # Responses API uses input list or messages
        payload: Dict[str, Any] = {
            "model": model,
            "input": messages,
            "stream": stream
        }

        if not strip_reasoning_param:
            lower_model = model.lower()
            if "gpt-5-pro" in lower_model:
                # Pro only supports high effort and cannot disable
                payload["reasoning"] = {"effort": "high"}
            elif reasoning_intent == "off":
                payload["reasoning"] = {"effort": "none"}
            elif reasoning_intent == "on":
                valid_efforts = ("low", "medium", "high", "xhigh", "max")
                eff = effort_level.lower() if effort_level.lower() in valid_efforts else "medium"
                payload["reasoning"] = {"effort": eff}
            # If "auto", we omit explicit reasoning to let model decide default

        return payload

    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        line_str = line.strip()
        if not line_str.startswith("data:"):
            return None
        data_str = line_str[5:].strip()
        if data_str == "[DONE]":
            return ParsedChunk(is_done=True)

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        event_type = event.get("type", "")
        if event_type == "response.done":
            return ParsedChunk(is_done=True, raw_event=event)

        # 1. Specialized streaming events from Responses API
        if event_type in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
            delta = event.get("delta", "")
            r_text = delta if isinstance(delta, str) else (delta.get("text", "") or delta.get("content", ""))
            return ParsedChunk(reasoning=r_text, raw_event=event)

        if event_type in ("response.text.delta", "response.output_text.delta"):
            delta = event.get("delta", "")
            c_text = delta if isinstance(delta, str) else (delta.get("text", "") or delta.get("content", ""))
            return ParsedChunk(content=c_text, raw_event=event)

        # 2. General delta object
        if "delta" in event:
            delta = event["delta"]
            if isinstance(delta, str):
                return ParsedChunk(content=delta, raw_event=event)
            elif isinstance(delta, dict):
                text = delta.get("text", "") or delta.get("content", "")
                reasoning = delta.get("reasoning", "") or delta.get("reasoning_text", "")
                return ParsedChunk(content=text, reasoning=reasoning, raw_event=event)

        # 3. Output item events (type == 'reasoning' vs type == 'message')
        item = event.get("item", {})
        item_type = item.get("type", "")
        if item_type == "reasoning":
            r_text = item.get("content", "") or item.get("summary", "") or item.get("reasoning_text", "")
            return ParsedChunk(reasoning=r_text, raw_event=event)
        elif item_type == "message":
            c_text = item.get("content", "")
            return ParsedChunk(content=c_text, raw_event=event)

        return None

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="API 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="Responses 端点或模型未找到。")
        if status_code == 429:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="超出调用频率或额度上限。")

        if status_code == 400:
            if "reasoning" in lower_body or "effort" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="reasoning.effort",
                    category="reasoning_param",
                    message="服务端不接受 reasoning.effort 参数。",
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
            "input": [{"role": "user", "content": "1+1="}],
            "reasoning": {"effort": "none"},
            "stream": False
        }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return ProbeResult(
                        state=ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.EFFORT_ENUM,
                        details="Responses API 已成功接受 reasoning.effort=none 参数 (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"Responses API 拒绝 reasoning 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

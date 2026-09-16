# -*- coding: utf-8 -*-
"""vLLM OpenAI-compatible Adapter.

Rules:
- Targets vLLM OpenAI-compatible Chat Completions endpoint.
- Uses chat_template_kwargs: {"enable_thinking": False/True}.
- Stream parses delta.reasoning or delta.reasoning_content.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class VLLMAdapter(ProviderAdapter):
    """Adapter for vLLM OpenAI-compatible endpoint."""

    protocol_name = "vllm_chat"

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
        if api_key and api_key.strip() and api_key != "sk-no-key":
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

        if not strip_reasoning_param:
            if reasoning_intent == "off":
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            elif reasoning_intent == "on":
                valid_eff = effort_level.lower() if effort_level.lower() in ("low", "medium", "high", "max") else "medium"
                payload["reasoning_effort"] = valid_eff
                payload["chat_template_kwargs"] = {"enable_thinking": True}

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
            # vLLM can use either delta.reasoning or delta.reasoning_content depending on reasoning parser
            reasoning = delta.get("reasoning", "") or delta.get("reasoning_content", "") or ""

        return ParsedChunk(content=content, reasoning=reasoning, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403):
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="vLLM 认证失败。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="vLLM 模型未加载或端点错误。")

        if status_code == 400:
            if "chat_template_kwargs" in lower_body or "enable_thinking" in lower_body:
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="chat_template_kwargs",
                    category="reasoning_param",
                    message="vLLM 部署模型模板不接受 chat_template_kwargs 参数。",
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
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False
        }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return ProbeResult(
                        state=ProbeState.CONFIRMED_SUPPORTED,
                        control_kind=ControlKind.TEMPLATE_KWARG,
                        details="vLLM 已确认支持 chat_template_kwargs.enable_thinking=false (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"vLLM 拒绝 chat_template_kwargs 参数: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

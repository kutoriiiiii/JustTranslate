# -*- coding: utf-8 -*-
"""Google Gemini Generate Content Adapter.

Rules:
- Targets Gemini Generate Content API (:streamGenerateContent).
- Gemini 2.5 Flash supports thinkingConfig.thinkingBudget = 0 to completely disable thinking.
- Gemini 2.5 Pro CANNOT set budget to 0 (will trigger 400 INVALID_ARGUMENT).
- Gemini 3.x uses thinkingConfig.thinkingLevel ("LOW", "MEDIUM", "HIGH"); minimal is not off.
- Plain models (Gemini 1.5, etc.) MUST OMIT thinkingConfig completely.
- Output: separates candidate parts with thought=true into reasoning.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.capability_registry import ControlKind, ProbeState
from core.network_utils import create_httpx_client


class GeminiAdapter(ProviderAdapter):
    """Adapter for Google Gemini Generate Content API."""

    protocol_name = "gemini_content"

    def get_endpoint_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if ":streamGenerateContent" in base:
            return base
        return f"{base}/models/{self.model}:streamGenerateContent?alt=sse"

    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if api_key and api_key.strip():
            headers["x-goog-api-key"] = api_key.strip()
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
        # Convert messages to Gemini contents structure
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        lower_model = model.lower()

        # Decide thinking config
        if not strip_reasoning_param:
            if "gemini-2.5-flash" in lower_model and "pro" not in lower_model and "lite" not in lower_model:
                if reasoning_intent == "off":
                    payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
                elif reasoning_intent == "on":
                    budget = budget_tokens if budget_tokens is not None else -1
                    payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": budget}
            elif "gemini-3" in lower_model:
                valid_efforts = ("minimal", "low", "medium", "high")
                eff = effort_level.lower() if effort_level.lower() in valid_efforts else "medium"
                payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": eff}
            elif "gemini-2.5-pro" in lower_model:
                if reasoning_intent == "on":
                    payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": budget_tokens or 1024}
                # Pro cannot disable with 0; if "off", omit thinkingConfig to avoid 400

        return payload

    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        line_str = line.strip()
        if not line_str.startswith("data:"):
            return None
        data_str = line_str[5:].strip()

        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        candidates = chunk.get("candidates", [])
        if not candidates:
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        content_out = ""
        reasoning_out = ""

        for part in parts:
            text = part.get("text", "")
            if part.get("thought", False):
                reasoning_out += text
            else:
                content_out += text

        return ParsedChunk(content=content_out, reasoning=reasoning_out, raw_event=chunk)

    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        lower_body = (response_body or "").lower()

        if status_code in (401, 403) or "api_key_invalid" in lower_body:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="auth", message="Google Gemini API 密钥无效。")
        if status_code == 404:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="not_found", message="Gemini 模型不存在。")
        if status_code == 429 or "resource_exhausted" in lower_body:
            return ReasoningErrorClassification(is_reasoning_parameter_error=False, category="quota", message="Gemini API 额度超限。")

        if status_code == 400 or "invalid_argument" in lower_body:
            if any(k in lower_body for k in ("thinkingconfig", "thinkingbudget", "thinkinglevel", "thinking")):
                return ReasoningErrorClassification(
                    is_reasoning_parameter_error=True,
                    offending_parameter="thinkingConfig",
                    category="reasoning_param",
                    message="Gemini 模型不接受 thinkingConfig 参数。",
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

        lower_model = model.lower()
        if "gemini-2.5-flash" in lower_model and "pro" not in lower_model:
            # Probe Flash with thinkingBudget=0 to verify disable support
            payload = {
                "contents": [{"parts": [{"text": "1+1="}]}],
                "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}
            }
        else:
            payload = {
                "contents": [{"parts": [{"text": "1+1="}]}]
            }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(timeout, connect=8.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    has_parts = bool(candidates and candidates[0].get("content", {}).get("parts"))
                    return ProbeResult(
                        state=ProbeState.CONFIRMED_SUPPORTED if "thinkingConfig" in payload.get("generationConfig", {}) else ProbeState.ACCEPTED_BUT_UNVERIFIED,
                        control_kind=ControlKind.TOKEN_BUDGET,
                        details="Gemini Generate Content 已确认接受参数 (HTTP 200)。",
                        raw_status_code=200
                    )
                else:
                    classification = self.classify_error(resp.status_code, resp.text)
                    if classification.is_reasoning_parameter_error:
                        return ProbeResult(
                            state=ProbeState.REJECTED_PARAMETER,
                            details=f"Gemini 拒绝 thinkingConfig: {resp.text[:120]}",
                            raw_status_code=resp.status_code
                        )
                    return ProbeResult(
                        state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA if classification.category in ("auth", "quota") else ProbeState.UNSUPPORTED,
                        details=classification.message or resp.text[:120],
                        raw_status_code=resp.status_code
                    )
        except Exception as e:
            return ProbeResult(state=ProbeState.UNAVAILABLE_AUTH_OR_QUOTA, details=f"连接异常: {str(e)}")

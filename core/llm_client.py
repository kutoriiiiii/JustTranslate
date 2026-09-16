# -*- coding: utf-8 -*-
"""OpenAI-compatible and multi-protocol LLM client supporting streaming, adapters, and reasoning control."""

import json
import time
from typing import Generator, List, Dict, Any, Optional, Callable
import httpx
from .network_utils import create_httpx_client, StreamController
from core.adapters import get_adapter, ProviderAdapter, ParsedChunk, ProbeResult
from core.capability_registry import CapabilityRegistry, ProbeState, ControlKind, CapabilityResolver


class LLMClient:
    """Client for querying LLM endpoints with protocol adapters, streaming, and network retry policies."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "default",
        timeout: float = 30.0,
        max_retries: int = 2,
        protocol: str = "openai_chat",
        provider: str = ""
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "sk-no-key-required"
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.protocol = protocol or "openai_chat"
        self.provider = provider or ""
        self.adapter: ProviderAdapter = get_adapter(
            protocol=self.protocol,
            provider=self.provider,
            model=self.model,
            base_url=self.base_url
        )

    def _get_headers(self) -> Dict[str, str]:
        return self.adapter.get_headers(self.api_key)

    def _get_endpoint(self) -> str:
        return self.adapter.get_endpoint_url(self.base_url)

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to the endpoint with a 30s timeout."""
        headers = self._get_headers()
        url = self._get_endpoint()

        # Build protocol-compliant minimal test payload
        if self.protocol in ("anthropic_messages", "gemini_content", "openai_responses"):
            payload = self.adapter.build_payload(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                reasoning_intent="off",
                temperature=0.3,
                stream=False,
                max_tokens=5
            )
        else:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "stream": False
            }

        try:
            with create_httpx_client(url, timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return True, "连接成功！"
                else:
                    classification = self.adapter.classify_error(resp.status_code, resp.text)
                    return False, f"HTTP {resp.status_code}: {classification.message or resp.text[:150]}"
        except httpx.ConnectError:
            return False, f"无法连接到服务地址: {self.base_url}。请确认本地模型服务或网络已开启。"
        except httpx.TimeoutException:
            return False, "连接或响应超时（已超过 30 秒上限）。"
        except Exception as e:
            return False, f"请求异常: {str(e)}"

    def probe_reasoning_capability(self, timeout: float = 15.0) -> ProbeResult:
        """Executes on-demand provider-specific thinking capability probe."""
        result = self.adapter.probe(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            timeout=timeout
        )
        registry = CapabilityRegistry.get_instance()
        registry.set_probe_cache(
            endpoint=self.base_url,
            protocol=self.protocol,
            model=self.model,
            probe_state=result.state,
            effective_kind=result.control_kind,
            details=result.details
        )
        return result

    def list_models(self) -> tuple[bool, List[str], str]:
        """探测当前 Base URL 下可用的模型列表，支持 OpenAI/Ollama/DeepSeek/vLLM/llama.cpp 等标准。
        返回: (成功布尔值, 模型ID列表, 状态或错误信息)
        """
        headers = {}
        if self.api_key and self.api_key.strip() and self.api_key != "sk-no-key-required":
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        headers["Accept"] = "application/json"

        # 尝试的端点优先级
        candidates = []
        clean_base = self.base_url.rstrip("/")
        if clean_base.endswith("/chat/completions"):
            clean_base = clean_base[:-17].rstrip("/")

        if clean_base.endswith("/v1"):
            candidates.append(f"{clean_base}/models")
            candidates.append(f"{clean_base[:-3]}/models")
        else:
            candidates.append(f"{clean_base}/v1/models")
            candidates.append(f"{clean_base}/models")
            candidates.append(f"{clean_base}/api/tags")  # Ollama 原生端点

        last_err = ""
        for url in candidates:
            for attempt in range(1, self.max_retries + 2):
                try:
                    with create_httpx_client(url, timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
                        resp = client.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            model_ids = self._extract_models_from_json(data)
                            if model_ids:
                                return True, model_ids, f"成功探测到 {len(model_ids)} 个可用模型！"
                            else:
                                break
                        elif resp.status_code in (401, 403):
                            return False, [], f"认证失败 (HTTP {resp.status_code})：请检查 API Key 是否正确。"
                        elif resp.status_code == 404:
                            break
                        else:
                            last_err = f"HTTP {resp.status_code}: {resp.text[:120]}"
                except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                    last_err = str(e)
                    if attempt <= self.max_retries:
                        time.sleep(1.0)
                        continue
                    break
                except Exception as e:
                    last_err = str(e)
                    break

        if last_err:
            return False, [], f"探测模型失败: {last_err}"
        return False, [], "未能从目标端点获取到模型列表，请确认该服务支持 /models 端点。"

    @staticmethod
    def _extract_models_from_json(json_data: Any) -> List[str]:
        models = []
        if isinstance(json_data, list):
            items = json_data
        elif isinstance(json_data, dict):
            items = json_data.get("data") or json_data.get("models") or []
        else:
            items = []

        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    models.append(item)
                elif isinstance(item, dict):
                    m_id = item.get("id") or item.get("name") or item.get("model")
                    if m_id:
                        models.append(str(m_id))
        return sorted(list(dict.fromkeys(models)))

    def stream_chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.3,
        controller: Optional[StreamController] = None,
        reasoning_intent: str = "auto",  # "auto", "on", "off"
        effort_level: str = "medium",
        budget_tokens: Optional[int] = None,
        reasoning_callback: Optional[Callable[[str], None]] = None
    ) -> Generator[str, None, None]:
        """Stream chat completions from LLM.
        
        Strict Error Handling & Retry Policies:
        - 400 is retried ONCE with stripped thinking parameters ONLY when error explicitly targets reasoning params.
        - If user explicitly selected deep thinking (reasoning_intent='on'), silent downgrade is FORBIDDEN.
        - Auth, 404, quota, and context length errors are NOT stripped or retried.
        - Reasoning stream is routed to reasoning_callback and never concatenated into translation content.
        """
        url = self._get_endpoint()
        headers = self._get_headers()
        # Check user intent conflict via CapabilityResolver
        if reasoning_intent in ("on", "off"):
            resolved = CapabilityResolver.resolve(
                provider=self.provider,
                protocol=self.protocol,
                model=self.model,
                endpoint=self.base_url,
                user_override=reasoning_intent
            )
            if resolved.error_conflict and reasoning_intent == "on":
                raise RuntimeError(f"无法满足深度思考要求：{resolved.error_conflict}")

        strip_reasoning = (reasoning_intent == "passthrough")
        retried_reasoning_downgrade = False

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_retries:
            if controller and controller.is_aborted:
                return

            attempt += 1

            payload = self.adapter.build_payload(
                model=self.model,
                messages=messages,
                reasoning_intent=reasoning_intent,
                effort_level=effort_level,
                budget_tokens=budget_tokens,
                temperature=temperature,
                stream=True,
                strip_reasoning_param=strip_reasoning
            )

            try:
                timeout_config = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout)
                client = create_httpx_client(url, timeout=timeout_config)
                if controller:
                    controller.active_client = client

                with client:
                    with client.stream("POST", url, json=payload, headers=headers) as response:
                        if controller:
                            controller.active_response = response
                            if controller.is_aborted:
                                return

                        if response.status_code != 200:
                            err_body = response.read().decode("utf-8", errors="ignore")[:400]
                            classification = self.adapter.classify_error(response.status_code, err_body, response.headers)

                            # Precise 400 reasoning parameter check
                            if classification.is_reasoning_parameter_error:
                                # Rule 9: Never silently downgrade when user explicitly chose deep thinking
                                if reasoning_intent == "on":
                                    raise RuntimeError(
                                        f"当前模型或端点不支持深度思考 ({classification.message})。根据用户设置，未进行静默降级。"
                                    )
                                # For auto or off: retry once without reasoning parameters if not retried yet
                                if not retried_reasoning_downgrade:
                                    retried_reasoning_downgrade = True
                                    strip_reasoning = True
                                    # Cache rejected state
                                    registry = CapabilityRegistry.get_instance()
                                    registry.set_probe_cache(
                                        endpoint=self.base_url,
                                        protocol=self.protocol,
                                        model=self.model,
                                        probe_state=ProbeState.REJECTED_PARAMETER,
                                        details=f"运行时接口拒绝思考参数: {classification.message}"
                                    )
                                    continue
                                else:
                                    raise RuntimeError(f"请求失败 (HTTP {response.status_code}): {err_body}")

                            # Auth / 404 / Quota / Context Length: Fail fast without retry
                            if classification.category in ("auth", "not_found", "quota", "context_length", "content_filter"):
                                raise RuntimeError(classification.message or f"HTTP {response.status_code}: {err_body}")

                            # Other 4xx client errors
                            if 400 <= response.status_code < 500:
                                raise RuntimeError(f"客户端请求错误 (HTTP {response.status_code}): {err_body}")

                            # 5xx server errors
                            raise RuntimeError(f"服务器返回错误 HTTP {response.status_code}: {err_body}")

                        # Stream reading
                        for line in response.iter_lines():
                            if controller and controller.is_aborted:
                                return
                            if not line:
                                continue

                            parsed = self.adapter.parse_stream_chunk(line)
                            if not parsed:
                                continue
                            if parsed.is_done:
                                return

                            # Route reasoning to callback, completely isolated from content
                            if parsed.reasoning and reasoning_callback:
                                reasoning_callback(parsed.reasoning)

                            # Yield pure translation content
                            if parsed.content:
                                yield parsed.content

                # Normal consumption completed
                return

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                if controller and controller.is_aborted:
                    return
                last_error = e
                if attempt <= self.max_retries:
                    time.sleep(1.0)
                    continue
                break
            except Exception as e:
                if controller and controller.is_aborted:
                    return
                last_error = e
                break

        if controller and controller.is_aborted:
            return

        if isinstance(last_error, httpx.TimeoutException):
            raise TimeoutError(f"请求在 30 秒内未能响应或连接超时（已自动重试 {attempt-1} 次）。请检查模型负载或网络。")
        elif isinstance(last_error, httpx.ConnectError):
            raise ConnectionError(f"无法连接到目标服务 {self.base_url}（已自动重试 {attempt-1} 次）。")
        else:
            raise RuntimeError(f"请求失败: {str(last_error)}")

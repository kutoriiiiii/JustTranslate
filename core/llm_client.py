"""OpenAI-compatible LLM client supporting local llama and external APIs with streaming and 30s timeout retry."""

import json
import time
from typing import Generator, List, Dict, Any, Optional
import httpx
from .network_utils import create_httpx_client, StreamController

class LLMClient:
    """Client for querying OpenAI-compatible endpoints with streaming & network retry policies."""

    def __init__(self, base_url: str, api_key: str = "", model: str = "default", timeout: float = 30.0, max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "sk-no-key-required"
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    def _get_endpoint(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        elif self.base_url.endswith("/chat/completions"):
            return self.base_url
        else:
            return f"{self.base_url}/v1/chat/completions"

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to the endpoint with a 30s timeout."""
        headers = self._get_headers()
        url = self._get_endpoint()
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
                    return False, f"HTTP {resp.status_code}: {resp.text[:150]}"
        except httpx.ConnectError:
            return False, f"无法连接到服务地址: {self.base_url}。请确认本地模型服务或网络已开启。"
        except httpx.TimeoutException:
            return False, f"连接或响应超时（已超过 30 秒上限）。"
        except Exception as e:
            return False, f"请求异常: {str(e)}"

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
                                # 虽返回 200 但未提取到模型，尝试下一个 candidate
                                break
                        elif resp.status_code in (401, 403):
                            return False, [], f"认证失败 (HTTP {resp.status_code})：请检查 API Key 是否正确。"
                        elif resp.status_code == 404:
                            # 端点不存在，尝试下一个 candidate
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
        return False, [], f"未能从目标端点获取到模型列表，请确认该服务支持 /models 端点。"

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
        controller: Optional[StreamController] = None
    ) -> Generator[str, None, None]:
        """Stream chat completions from LLM. Implements 30s timeout, StreamController cancellation, and retry on failure."""
        url = self._get_endpoint()
        headers = self._get_headers()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_retries:
            if controller and controller.is_aborted:
                return

            attempt += 1
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
                            err_body = response.read().decode("utf-8", errors="ignore")[:200]
                            raise RuntimeError(f"服务器返回错误 HTTP {response.status_code}: {err_body}")

                        for line in response.iter_lines():
                            if controller and controller.is_aborted:
                                return
                            if not line:
                                continue
                            line_str = line.strip()
                            if line_str.startswith("data:"):
                                data_str = line_str[len("data:"):].strip()
                                if data_str == "[DONE]":
                                    return
                                try:
                                    chunk = json.loads(data_str)
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    continue
                # 正常消费结束，直接退出重试循环
                return

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, RuntimeError) as e:
                if controller and controller.is_aborted:
                    return
                last_error = e
                if attempt <= self.max_retries:
                    # 遭遇网络异常，自动触发重试
                    time.sleep(1.0)
                    continue
                else:
                    break
            except Exception as e:
                if controller and controller.is_aborted:
                    return
                last_error = e
                break

        if controller and controller.is_aborted:
            return

        # 超过重试上限或非网络类异常
        if isinstance(last_error, httpx.TimeoutException):
            raise TimeoutError(f"请求在 30 秒内未能响应或连接超时（已自动重试 {attempt-1} 次）。请检查模型负载或网络。")
        elif isinstance(last_error, httpx.ConnectError):
            raise ConnectionError(f"无法连接到目标服务 {self.base_url}（已自动重试 {attempt-1} 次）。")
        else:
            raise RuntimeError(f"请求失败: {str(last_error)}")

# -*- coding: utf-8 -*-
"""Adapter Factory for JustTranslate LLM Protocols.

Resolves specific ProviderAdapter instances based on provider, protocol, model, and base_url.
Strictly avoids merging distinct provider protocols into a single rule.
"""

from typing import Optional
from core.adapters.base import ProviderAdapter, ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.adapters.openai_chat import OpenAIChatAdapter
from core.adapters.openai_responses import OpenAIResponsesAdapter
from core.adapters.anthropic import AnthropicAdapter
from core.adapters.gemini import GeminiAdapter
from core.adapters.deepseek import DeepSeekAdapter
from core.adapters.dashscope import DashScopeAdapter
from core.adapters.zhipu import ZhipuAdapter
from core.adapters.volcengine import VolcengineAdapter
from core.adapters.ollama import OllamaAdapter
from core.adapters.vllm import VLLMAdapter
from core.adapters.generic_openai import GenericOpenAIAdapter


def get_adapter(
    protocol: str = "openai_chat",
    provider: str = "",
    model: str = "",
    base_url: str = ""
) -> ProviderAdapter:
    """Factory creating the specific adapter instance based on protocol, provider, and model."""
    proto = (protocol or "").strip().lower()
    prov = (provider or "").strip().lower()
    url = (base_url or "").strip().lower()

    # 1. Anthropic Messages API
    if proto == "anthropic_messages" or prov == "anthropic" or "api.anthropic.com" in url:
        return AnthropicAdapter(provider="anthropic", model=model)

    # 2. Google Gemini Generate Content API
    if proto == "gemini_content" or prov == "gemini" or "generativelanguage.googleapis.com" in url:
        return GeminiAdapter(provider="gemini", model=model)

    # 3. OpenAI Responses API
    if proto == "openai_responses" or (prov == "openai" and "responses" in proto):
        return OpenAIResponsesAdapter(provider="openai", model=model)

    # 4. Ollama Native API
    if proto == "ollama_native" or prov == "ollama" or ":11434" in url:
        return OllamaAdapter(provider="ollama", model=model)

    # 5. vLLM OpenAI-compatible API
    if proto == "vllm_chat" or prov == "vllm":
        return VLLMAdapter(provider="vllm", model=model)

    # 6. DeepSeek Official API
    if prov == "deepseek" or "api.deepseek.com" in url:
        return DeepSeekAdapter(provider="deepseek", model=model)

    # 7. Alibaba DashScope / Qwen
    if prov in ("dashscope", "aliyun", "qwen") or "dashscope.aliyuncs.com" in url:
        return DashScopeAdapter(provider="dashscope", model=model)

    # 8. Zhipu AI / Z.AI
    if prov in ("zhipu", "z_ai", "glm") or "bigmodel.cn" in url:
        return ZhipuAdapter(provider="zhipu", model=model)

    # 9. Volcengine Ark
    if prov in ("volcengine", "ark", "doubao") or "volces.com" in url:
        return VolcengineAdapter(provider="volcengine", model=model)

    # 10. OpenAI Official Chat Completions
    if prov == "openai" or "api.openai.com" in url:
        return OpenAIChatAdapter(provider="openai", model=model)

    # 11. Generic OpenAI-compatible
    if proto in ("openai_chat", "generic_openai", ""):
        return GenericOpenAIAdapter(provider="generic", model=model)

    return GenericOpenAIAdapter(provider=prov or "generic", model=model)

# -*- coding: utf-8 -*-
"""Comprehensive tests for Thinking / Reasoning capability adaptation (v3 Cleaned).

Strictly covers:
1. Static / Registry verification (GPT-5.6, Claude 5/4.6, Gemini 3 levels, DeepSeek Flash, Qwen3.8, etc.)
2. Runtime CapabilityResolver 6-level priority order & user conflict detection
3. Mock / Fixture verification for all adapters (OpenAI Chat/Responses, Anthropic, Gemini, DeepSeek, DashScope, Zhipu, Ark, Ollama, vLLM, Generic)
4. Safe 400 Fallback (only retry on reasoning error, forbidden silent downgrade when user chose 'on', auth/404/quota fail-fast)
5. Probe Multi-State verification (no false confirmed on 200 without trace, rejected, forced_on)
6. Fast translate criteria & 3-level cascade overrides
"""

import json
import time
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from core.capability_registry import (
    CapabilityRegistry, RegistryEntry, ReasoningStatus, ControlKind, ProbeState,
    ProbeCacheEntry, EvidenceSource, CapabilityResolver, ResolvedCapability
)
from core.adapters import (
    get_adapter, OpenAIChatAdapter, OpenAIResponsesAdapter, AnthropicAdapter,
    GeminiAdapter, DeepSeekAdapter, DashScopeAdapter, ZhipuAdapter,
    VolcengineAdapter, OllamaAdapter, VLLMAdapter, GenericOpenAIAdapter
)
from core.adapters.base import ParsedChunk, ReasoningErrorClassification, ProbeResult
from core.llm_client import LLMClient
from core.text_utils import is_fast_translate_eligible


class TestCapabilityRegistryV3(unittest.TestCase):
    """1. Static / Registry & Resolver verification."""

    def setUp(self):
        self.tmp_cache = Path(__file__).parent / "tmp_probe_cache.json"
        self.registry = CapabilityRegistry(cache_file=self.tmp_cache)

    def tearDown(self):
        if self.tmp_cache.exists():
            try:
                self.tmp_cache.unlink()
            except Exception:
                pass

    def test_registry_schema_and_entries(self):
        """Checks registry entries possess required v3 fields and valid metadata."""
        self.assertTrue(len(self.registry.entries) >= 15)
        for entry in self.registry.entries:
            self.assertTrue(entry.provider)
            self.assertTrue(entry.protocol)
            self.assertTrue(entry.model_family)
            self.assertTrue(entry.model_patterns)
            self.assertTrue(entry.authority_url.startswith("http"))
            self.assertEqual(entry.checked_at, "2026-09-16")
            self.assertTrue(entry.authority_scope in ("exact_model", "model_family", "protocol", "provider"))
            self.assertTrue(entry.evidence_level in ("official_exact", "official_family", "provider_metadata", "probe", "heuristic", "unknown"))

    def test_gpt56_models_fast_path(self):
        """Verifies GPT-5.6 Sol / Terra / Luna in Responses and Chat."""
        # Responses
        resp_entry = self.registry.match("openai", "openai_responses", "gpt-5.6-sol")
        self.assertIsNotNone(resp_entry)
        self.assertTrue(resp_entry.can_disable)
        self.assertIn("none", resp_entry.allowed_effort_levels)
        self.assertIn("max", resp_entry.allowed_effort_levels)

        # Chat
        chat_entry = self.registry.match("openai", "openai_chat", "gpt-5.6-terra")
        self.assertIsNotNone(chat_entry)
        self.assertEqual(chat_entry.control_path, "reasoning_effort")
        self.assertTrue(chat_entry.can_disable)

    def test_claude_family_separation(self):
        """Verifies Claude Sonnet 5, Opus 5, Fable 5, and 4.6/4.7 distinct semantics."""
        # Claude Sonnet 5 defaults on and needs type: disabled
        sonnet5 = self.registry.match("anthropic", "anthropic_messages", "claude-sonnet-5-20260601")
        self.assertIsNotNone(sonnet5)
        self.assertEqual(sonnet5.off_strategy, "disabled_type")
        self.assertEqual(sonnet5.default_when_omitted, "on")

        # Claude 4.6 defaults off / omits thinking
        claude46 = self.registry.match("anthropic", "anthropic_messages", "claude-sonnet-4-6")
        self.assertIsNotNone(claude46)
        self.assertEqual(claude46.off_strategy, "omit_thinking")

        # Claude Fable 5 forced on
        fable5 = self.registry.match("anthropic", "anthropic_messages", "claude-fable-5")
        self.assertIsNotNone(fable5)
        self.assertFalse(fable5.can_disable)
        self.assertIn(ReasoningStatus.FORCED_ON, fable5.supported_statuses)

        # Claude 3.7 retired
        c37 = self.registry.match("anthropic", "anthropic_messages", "claude-3-7-sonnet-20250219")
        self.assertIsNotNone(c37)
        self.assertEqual(c37.status, "deprecated")

    def test_gemini_no_med_and_levels_per_model(self):
        """Verifies Gemini 3 does not have MED and levels are model-specific."""
        for entry in self.registry.entries:
            if entry.provider == "gemini":
                self.assertNotIn("MED", entry.allowed_effort_levels)
                self.assertNotIn("MED", entry.supported_levels)

        # Gemini 3.8 Flash supports low, medium, high
        g38 = self.registry.match("gemini", "gemini_content", "gemini-3.8-flash")
        self.assertIsNotNone(g38)
        self.assertEqual(g38.supported_levels, ["low", "medium", "high"])
        self.assertFalse(g38.can_disable)

        # Gemini 3.6 Flash supports minimal, low, medium, high
        g36 = self.registry.match("gemini", "gemini_content", "gemini-3.6-flash")
        self.assertIsNotNone(g36)
        self.assertIn("minimal", g36.supported_levels)
        self.assertFalse(g36.can_disable)

        # Gemini 2.5 Flash vs Pro
        g25f = self.registry.match("gemini", "gemini_content", "gemini-2.5-flash")
        self.assertTrue(g25f.can_disable)
        g25p = self.registry.match("gemini", "gemini_content", "gemini-2.5-pro")
        self.assertFalse(g25p.can_disable)

    def test_deepseek_flash_and_v4_pro(self):
        """Verifies DeepSeek Flash and V4-Pro are primary fast path models."""
        ds_flash = self.registry.match("deepseek", "openai_chat", "deepseek-flash")
        self.assertIsNotNone(ds_flash)
        self.assertTrue(ds_flash.can_disable)
        self.assertEqual(ds_flash.off_strategy, "disabled_type")

        ds_v4 = self.registry.match("deepseek", "openai_chat", "deepseek-v4-pro")
        self.assertIsNotNone(ds_v4)
        self.assertTrue(ds_v4.can_disable)

    def test_zhipu_glm47_can_disable(self):
        """Verifies GLM-4.7 is NOT forced_on and can be disabled via type: disabled."""
        glm47 = self.registry.match("zhipu", "openai_chat", "glm-4.7")
        self.assertIsNotNone(glm47)
        self.assertTrue(glm47.can_disable)
        self.assertEqual(glm47.off_strategy, "disabled_type")

    def test_zhipu_glm53_forced_on(self):
        """Verifies GLM-5.3 and GLM-5.3-Flash are marked forced_on with reasoning_effort levels."""
        glm53 = self.registry.match("zhipu", "openai_chat", "glm-5.3")
        self.assertIsNotNone(glm53)
        self.assertFalse(glm53.can_disable)
        self.assertEqual(glm53.default_level, "max")
        self.assertEqual(glm53.allowed_effort_levels, ["low", "high", "max"])

        glm53_flash = self.registry.match("zhipu", "openai_chat", "glm-5.3-flash")
        self.assertIsNotNone(glm53_flash)
        self.assertFalse(glm53_flash.can_disable)

    def test_volcengine_no_ep_wildcard(self):
        """Verifies ep-* is NOT matched as an official reasoning model."""
        ep_entry = self.registry.match("volcengine", "openai_chat", "ep-20250101-xyz")
        self.assertIsNone(ep_entry)

        doubao = self.registry.match("volcengine", "openai_chat", "doubao-1.5-pro-32k")
        self.assertIsNotNone(doubao)
        self.assertTrue(doubao.can_disable)

    def test_capability_resolver_6_levels(self):
        """Tests the unified 6-level resolution priority."""
        # Level 1: User override
        res_user = CapabilityResolver.resolve("openai", "openai_chat", "gpt-4o", user_override="off", registry=self.registry)
        self.assertEqual(res_user.evidence_source, EvidenceSource.USER_OVERRIDE)
        self.assertTrue(res_user.can_disable)

        # Level 1: User conflict (user asks 'on' for non-reasoning model)
        res_conflict = CapabilityResolver.resolve("openai", "openai_chat", "gpt-4o", user_override="on", registry=self.registry)
        self.assertIsNotNone(res_conflict.error_conflict)
        self.assertFalse(res_conflict.can_enable)

        # Level 2: Official registry
        res_reg = CapabilityResolver.resolve("openai", "openai_responses", "gpt-5.6-sol", registry=self.registry)
        self.assertEqual(res_reg.evidence_source, EvidenceSource.OFFICIAL_FAMILY)
        self.assertTrue(res_reg.can_disable)
        self.assertTrue(res_reg.can_enable)

        # Level 3: Provider metadata
        res_meta = CapabilityResolver.resolve(
            "custom", "openai_chat", "custom-model",
            provider_metadata={"reasoning_supported": True, "can_disable": True, "effort": "low"},
            registry=self.registry
        )
        self.assertEqual(res_meta.evidence_source, EvidenceSource.PROVIDER_METADATA)
        self.assertTrue(res_meta.can_enable)

        # Level 4: Probe cache
        self.registry.set_probe_cache("http://local", "openai_chat", "cached-m", ProbeState.CONFIRMED_SUPPORTED, ControlKind.BOOLEAN)
        res_probe = CapabilityResolver.resolve("custom", "openai_chat", "cached-m", endpoint="http://local", registry=self.registry)
        self.assertEqual(res_probe.evidence_source, EvidenceSource.PROBE_CONFIRMED)

        # Level 5: Heuristic hint
        res_hint = CapabilityResolver.resolve("custom", "openai_chat", "my-deepseek-r1-clone", registry=self.registry)
        self.assertEqual(res_hint.evidence_source, EvidenceSource.HEURISTIC_HINT)
        self.assertFalse(res_hint.can_enable)  # Does NOT inject parameters!

        # Level 6: Safe default
        res_default = CapabilityResolver.resolve("custom", "openai_chat", "plain-unknown", registry=self.registry)
        self.assertEqual(res_default.evidence_source, EvidenceSource.UNKNOWN)
        self.assertEqual(res_default.control_kind, ControlKind.NONE)
        self.assertFalse(res_default.can_enable)

    def test_passthrough_user_override(self):
        """Verifies that user_override='passthrough' sets control_kind=NONE and does not conflict."""
        res = CapabilityResolver.resolve("zhipu", "openai_chat", "glm-5.3", user_override="passthrough", registry=self.registry)
        self.assertEqual(res.evidence_source, EvidenceSource.USER_OVERRIDE)
        self.assertEqual(res.control_kind, ControlKind.NONE)
        self.assertIsNone(res.error_conflict)
        self.assertTrue(res.can_disable)



class TestProviderAdaptersV3(unittest.TestCase):
    """3. Mock / Fixture verification for all adapters."""

    def test_openai_chat_adapter(self):
        adapter = OpenAIChatAdapter(provider="openai", model="gpt-5.6-sol")
        # GPT-5.6 supports reasoning_effort: none
        payload_off = adapter.build_payload("gpt-5.6-sol", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["reasoning_effort"], "none")

        payload_on = adapter.build_payload("gpt-5.6-sol", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="xhigh")
        self.assertEqual(payload_on["reasoning_effort"], "xhigh")

        # o3-mini on Chat: cannot disable, temperature must be omitted
        payload_o3 = adapter.build_payload("o3-mini", [{"role": "user", "content": "hi"}], reasoning_intent="off", effort_level="low")
        self.assertEqual(payload_o3["reasoning_effort"], "low")
        self.assertNotIn("temperature", payload_o3)

        # Standard gpt-4o: MUST NOT contain reasoning_effort
        payload_4o = adapter.build_payload("gpt-4o", [{"role": "user", "content": "hi"}], reasoning_intent="on", temperature=0.7)
        self.assertNotIn("reasoning_effort", payload_4o)

    def test_openai_responses_adapter(self):
        adapter = OpenAIResponsesAdapter(provider="openai", model="gpt-5.6")
        payload_off = adapter.build_payload("gpt-5.6", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["reasoning"]["effort"], "none")

        payload_on = adapter.build_payload("gpt-5.6", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="max")
        self.assertEqual(payload_on["reasoning"]["effort"], "max")

        # GPT-5-Pro forced high
        payload_pro = adapter.build_payload("gpt-5-pro", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_pro["reasoning"]["effort"], "high")

        # Stream parsing: response.reasoning_text.delta
        chunk_r = adapter.parse_stream_chunk('data: {"type": "response.reasoning_text.delta", "delta": "thinking step"}')
        self.assertEqual(chunk_r.reasoning, "thinking step")
        self.assertEqual(chunk_r.content, "")

    def test_anthropic_adapter(self):
        adapter = AnthropicAdapter(provider="anthropic", model="claude-sonnet-5")
        # Claude Sonnet 5 Off: must send thinking: {type: disabled}
        payload_off_5 = adapter.build_payload("claude-sonnet-5", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off_5["thinking"]["type"], "disabled")

        # Claude 4.6 Off: must completely OMIT thinking
        payload_off_46 = adapter.build_payload("claude-sonnet-4-6", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertNotIn("thinking", payload_off_46)

        # Claude 4.6 On: adaptive effort
        payload_on_46 = adapter.build_payload("claude-sonnet-4-6", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="high")
        self.assertEqual(payload_on_46["thinking"]["type"], "adaptive")
        self.assertEqual(payload_on_46["output_config"]["effort"], "high")
        self.assertEqual(payload_on_46["temperature"], 1.0)

    def test_gemini_adapter(self):
        adapter = GeminiAdapter(provider="gemini", model="gemini-2.5-flash")
        # 2.5 Flash Off: thinkingBudget = 0
        payload_off = adapter.build_payload("gemini-2.5-flash", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0)

        # 2.5 Pro: cannot set thinkingBudget=0
        payload_pro = adapter.build_payload("gemini-2.5-pro", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertNotIn("thinkingConfig", payload_pro.get("generationConfig", {}))

        # Gemini 3: thinkingLevel clean enum without MED
        payload_g3 = adapter.build_payload("gemini-3.8-flash", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="high")
        self.assertEqual(payload_g3["generationConfig"]["thinkingConfig"]["thinkingLevel"], "high")

    def test_deepseek_adapter(self):
        adapter = DeepSeekAdapter(provider="deepseek", model="deepseek-flash")
        payload_off = adapter.build_payload("deepseek-flash", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["thinking"]["type"], "disabled")

        payload_on = adapter.build_payload("deepseek-flash", [{"role": "user", "content": "hi"}], reasoning_intent="on")
        self.assertEqual(payload_on["thinking"]["type"], "enabled")
        self.assertGreaterEqual(payload_on["top_p"], 0.95)

    def test_dashscope_adapter(self):
        adapter = DashScopeAdapter(provider="dashscope", model="qwen3.8")
        # Qwen3.8 reasoning_effort = none
        payload_off = adapter.build_payload("qwen3.8", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["reasoning_effort"], "none")

        # Qwen3.8 reasoning_effort and thinking_budget mutual exclusion
        payload_on = adapter.build_payload("qwen3.8", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="high")
        self.assertEqual(payload_on["reasoning_effort"], "xhigh")
        self.assertNotIn("thinking_budget", payload_on)

    def test_zhipu_adapter(self):
        adapter = ZhipuAdapter(provider="zhipu", model="glm-4.7")
        # GLM-4.7 can disable
        payload_off = adapter.build_payload("glm-4.7", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["thinking"]["type"], "disabled")

        # GLM-5.3 forced_on, off gracefully degrades to reasoning_effort: low to minimize tokens/latency
        payload_53_off = adapter.build_payload("glm-5.3", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_53_off["thinking"]["type"], "enabled")
        self.assertEqual(payload_53_off["reasoning_effort"], "low")
        self.assertEqual(payload_53_off["top_p"], 0.95)
        self.assertEqual(payload_53_off["temperature"], 1.0)

        # GLM-5.3-Flash on intent maps reasoning_effort
        payload_flash_on = adapter.build_payload("glm-5.3-flash", [{"role": "user", "content": "hi"}], reasoning_intent="on", effort_level="high")
        self.assertEqual(payload_flash_on["thinking"]["type"], "enabled")
        self.assertEqual(payload_flash_on["reasoning_effort"], "high")

    def test_volcengine_adapter(self):
        adapter = VolcengineAdapter(provider="volcengine", model="doubao-1.5-pro")
        payload_off = adapter.build_payload("doubao-1.5-pro", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["reasoning_effort"], "none")

        # Arbitrary ep-* does not blindly inject reasoning_effort on off
        payload_ep = adapter.build_payload("ep-unknown-model", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertNotIn("reasoning_effort", payload_ep)

    def test_ollama_adapter(self):
        adapter = OllamaAdapter(provider="ollama", model="qwen3")
        payload_off = adapter.build_payload("qwen3", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertFalse(payload_off["think"])

        # GPT-OSS effort level
        payload_oss = adapter.build_payload("gpt-oss:20b", [{"role": "user", "content": "hi"}], reasoning_intent="off", effort_level="medium")
        self.assertEqual(payload_oss["think"], "medium")

        # Unknown model does not inject think: false
        payload_plain = adapter.build_payload("llama3", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertNotIn("think", payload_plain)

    def test_vllm_adapter(self):
        adapter = VLLMAdapter(provider="vllm", model="qwen-coder")
        payload_off = adapter.build_payload("qwen-coder", [{"role": "user", "content": "hi"}], reasoning_intent="off")
        self.assertEqual(payload_off["chat_template_kwargs"]["enable_thinking"], False)

    def test_generic_openai_adapter_conservative_default(self):
        adapter = GenericOpenAIAdapter(provider="generic", model="unknown-proxy-model")
        payload = adapter.build_payload("unknown-proxy-model", [{"role": "user", "content": "hi"}], reasoning_intent="on")
        self.assertNotIn("thinking", payload)
        self.assertNotIn("reasoning_effort", payload)


class TestSafeFallbackAndRetry(unittest.TestCase):
    """4. Safe 400 Fallback & Error Classification."""

    def test_classify_reasoning_error_vs_auth_quota(self):
        adapter = OpenAIChatAdapter(provider="openai", model="o3-mini")

        err_reasoning = adapter.classify_error(400, '{"error": {"message": "Invalid value for reasoning_effort: none"}}')
        self.assertTrue(err_reasoning.is_reasoning_parameter_error)
        self.assertTrue(err_reasoning.can_retry_without_reasoning)

        err_auth = adapter.classify_error(401, '{"error": {"message": "Incorrect API key provided"}}')
        self.assertFalse(err_auth.is_reasoning_parameter_error)
        self.assertEqual(err_auth.category, "auth")

    @patch("core.llm_client.create_httpx_client")
    def test_no_silent_downgrade_when_user_chose_on(self, mock_client_factory):
        """Rule: When user explicitly chose deep thinking, silent downgrade is FORBIDDEN."""
        client = LLMClient("http://api.test/v1", model="o3-mini", protocol="openai_chat")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}
        mock_resp.read.return_value = b'{"error": "reasoning_effort unsupported"}'

        mock_http = MagicMock()
        mock_http.stream.return_value.__enter__.return_value = mock_resp
        mock_client_factory.return_value = mock_http

        with self.assertRaises(RuntimeError) as ctx:
            list(client.stream_chat(
                [{"role": "user", "content": "hi"}],
                reasoning_intent="on"
            ))
        self.assertIn("未进行静默降级", str(ctx.exception))


class TestFastTranslateCriteria(unittest.TestCase):
    """6. Fast translate criteria."""

    def test_fast_translate_threshold_and_sentences(self):
        self.assertTrue(is_fast_translate_eligible("Hello world", threshold_chars=150, threshold_sentences=2))
        self.assertTrue(is_fast_translate_eligible("Good morning! How are you?", threshold_chars=150, threshold_sentences=2))
        self.assertFalse(is_fast_translate_eligible("One. Two. Three.", threshold_chars=150, threshold_sentences=2))
        long_text = "This is a long sentence. " * 15
        self.assertFalse(is_fast_translate_eligible(long_text, threshold_chars=150, threshold_sentences=2))
        self.assertFalse(is_fast_translate_eligible("Hello", threshold_chars=0))

    def test_fast_translate_structural_exemptions(self):
        self.assertFalse(is_fast_translate_eligible("```python\nprint(1)\n```", threshold_chars=150))
        self.assertFalse(is_fast_translate_eligible("Formula is $E=mc^2$", threshold_chars=150))
        self.assertFalse(is_fast_translate_eligible("- Item 1\n- Item 2", threshold_chars=150))


if __name__ == "__main__":
    unittest.main()

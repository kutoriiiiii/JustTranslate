# -*- coding: utf-8 -*-
"""Model Capability Registry & Probe Cache.

Strictly follows JustTranslate Thinking Mode Correction Doc v3:
- Models capability by: provider + protocol/endpoint + model_family + model_id/pattern.
- Distinguishes exact vs family entries, evidence levels, and probe states.
- Does NOT treat HTTP 200 as confirmation of thinking support.
- Implements endpoint-level cache with TTL.
- Features unified 6-level CapabilityResolver priority.
- Cleaned and updated to 2026-09-16 official models (GPT-5.6, Claude 5/4.6, Gemini 3, DeepSeek Flash/V4, etc.).
"""

import fnmatch
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ReasoningStatus(str, Enum):
    """Reasoning capability status."""
    OFF_SUPPORTED = "off_supported"              # Explicitly supports disabling thinking
    ON_SUPPORTED = "on_supported"                # Explicitly supports enabling thinking
    ADAPTIVE_SUPPORTED = "adaptive_supported"    # Supports dynamic/adaptive thinking
    EFFORT_SUPPORTED = "effort_supported"        # Supports discrete effort levels (low/med/high)
    BUDGET_SUPPORTED = "budget_supported"        # Supports token budget integer
    FORCED_ON = "forced_on"                      # Pure reasoning model; cannot disable thinking
    UNSUPPORTED = "unsupported"                  # Plain model; does not support thinking
    CONDITIONAL = "conditional"                  # Model/template-dependent
    UNKNOWN = "unknown"                          # Insufficient evidence


class ControlKind(str, Enum):
    """Protocol payload control type for thinking/reasoning."""
    NONE = "none"
    BOOLEAN = "boolean"                          # e.g. think: false / true
    EFFORT_ENUM = "effort_enum"                  # e.g. reasoning.effort / reasoning_effort: "low"
    TOKEN_BUDGET = "token_budget"                # e.g. thinking_budget: 1024 / thinkingBudget: 0
    ADAPTIVE_EFFORT = "adaptive_effort"          # e.g. Anthropic adaptive thinking with effort
    THINKING_OBJECT = "thinking_object"          # e.g. thinking: {"type": "enabled"/"disabled"}
    TEMPLATE_KWARG = "template_kwarg"            # e.g. chat_template_kwargs: {"enable_thinking": False}
    MODEL_TEMPLATE_DEPENDENT = "model_template_dependent"
    MODEL_SWITCH = "model_switch"                # Must switch model ID to toggle reasoning
    PROVIDER_SPECIFIC = "provider_specific"


class ProbeState(str, Enum):
    """Result of an on-demand probe."""
    CONFIRMED_SUPPORTED = "confirmed_supported"          # Response contained clear reasoning signal/structure
    ACCEPTED_BUT_UNVERIFIED = "accepted_but_unverified"  # HTTP 200 returned but no reasoning signal verified
    REJECTED_PARAMETER = "rejected_parameter"            # Server returned 400 specifically pointing to thinking param
    FORCED_ON = "forced_on"                              # Server indicated thinking is mandatory
    UNSUPPORTED = "unsupported"                          # Endpoint/model clearly does not support thinking
    UNAVAILABLE_AUTH_OR_QUOTA = "unavailable_auth_quota" # Auth, quota, or 404 failure during probe
    NOT_RUN = "not_run"


class EvidenceSource(str, Enum):
    """Source of truth hierarchy."""
    USER_OVERRIDE = "user_override"          # Explicit user configuration per model/endpoint
    OFFICIAL_EXACT = "official_exact"        # Official vendor doc for exact model ID
    OFFICIAL_FAMILY = "official_family"      # Official vendor doc for model family
    PROVIDER_METADATA = "provider_metadata"  # Returned by /models or provider schema
    PROBE_CONFIRMED = "probe_confirmed"      # Probed with strong response verification
    PROBE_ACCEPTED = "probe_accepted"        # Probed with 200 but without reasoning trace confirmation
    HEURISTIC_HINT = "heuristic_hint"        # Name keyword guess only; never dictates payload
    UNKNOWN = "unknown"


@dataclass
class RegistryEntry:
    """Entry in the Model Capability Registry."""
    provider: str
    protocol: str
    model_family: str
    model_patterns: List[str]
    model_exclusions: List[str] = field(default_factory=list)
    status: str = "active"  # "active", "legacy", "deprecated", "conditional"
    can_disable: bool = False
    supported_statuses: List[ReasoningStatus] = field(default_factory=list)
    control_kind: ControlKind = ControlKind.NONE
    control_path: str = ""
    allowed_effort_levels: List[str] = field(default_factory=list)
    supported_levels: List[str] = field(default_factory=list)
    default_level: str = ""
    default_when_omitted: str = ""  # "on", "off"
    off_strategy: str = ""          # "omit_thinking", "disabled_type", "effort_none", "budget_0", "think_false"
    disable_payload: Dict[str, Any] = field(default_factory=dict)
    disable_constraints: Dict[str, Any] = field(default_factory=dict)
    mutually_exclusive_parameters: List[List[str]] = field(default_factory=list)
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None
    constraints: List[str] = field(default_factory=list)
    output_reasoning_paths: List[str] = field(default_factory=list)
    output_usage_paths: List[str] = field(default_factory=list)
    authority_url: str = ""
    authority_scope: str = "model_family"  # "exact_model", "model_family", "protocol", "provider"
    evidence_level: str = "official_family"  # "official_exact", "official_family", "provider_metadata", etc.
    checked_at: str = "2026-09-16"
    expires_at: str = "2026-10-16"
    notes: str = ""

    def matches_model(self, model_name: str) -> bool:
        """Checks if a model name matches this registry entry."""
        if not model_name:
            return False
        model_name = model_name.strip()

        # Check exclusions first
        for excl in self.model_exclusions:
            if fnmatch.fnmatch(model_name.lower(), excl.lower()):
                return False

        for pat in self.model_patterns:
            if fnmatch.fnmatch(model_name.lower(), pat.lower()):
                return True
        return False


@dataclass
class ProbeCacheEntry:
    """Cached probe result for a specific base_url + protocol + model."""
    endpoint: str
    protocol: str
    model: str
    probe_state: ProbeState
    effective_kind: ControlKind = ControlKind.NONE
    observed_at: float = 0.0
    ttl_seconds: float = 86400.0 * 7  # 7 days default
    evidence: str = EvidenceSource.UNKNOWN.value
    details: str = ""

    def is_expired(self) -> bool:
        if self.observed_at <= 0:
            return True
        return (time.time() - self.observed_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "model": self.model,
            "probe_state": self.probe_state.value if isinstance(self.probe_state, ProbeState) else str(self.probe_state),
            "effective_kind": self.effective_kind.value if isinstance(self.effective_kind, ControlKind) else str(self.effective_kind),
            "observed_at": self.observed_at,
            "ttl_seconds": self.ttl_seconds,
            "evidence": self.evidence,
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProbeCacheEntry":
        return cls(
            endpoint=data.get("endpoint", ""),
            protocol=data.get("protocol", "openai_chat"),
            model=data.get("model", ""),
            probe_state=ProbeState(data.get("probe_state", ProbeState.NOT_RUN.value)),
            effective_kind=ControlKind(data.get("effective_kind", ControlKind.NONE.value)),
            observed_at=data.get("observed_at", 0.0),
            ttl_seconds=data.get("ttl_seconds", 86400.0 * 7),
            evidence=data.get("evidence", EvidenceSource.UNKNOWN.value),
            details=data.get("details", "")
        )


# ============================================================================
# OFFICIAL BASELINE REGISTRY (VERIFIED 2026-09-16, CLEANED v3)
# ============================================================================

OFFICIAL_REGISTRY: List[RegistryEntry] = [
    # ------------------------------------------------------------------------
    # OpenAI: Responses API
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="openai",
        protocol="openai_responses",
        model_family="gpt-5.6",
        model_patterns=["gpt-5.6", "gpt-5.6-sol*", "gpt-5.6-terra*", "gpt-5.6-luna*"],
        model_exclusions=["gpt-5-pro*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning.effort",
        allowed_effort_levels=["none", "low", "medium", "high", "xhigh", "max"],
        supported_levels=["none", "low", "medium", "high", "xhigh", "max"],
        default_level="medium",
        default_when_omitted="on",
        off_strategy="effort_none",
        output_reasoning_paths=["output[type=reasoning].content", "output[type=reasoning].summary"],
        output_usage_paths=["usage.output_tokens_details.reasoning_tokens"],
        authority_url="https://platform.openai.com/docs/api-reference/responses",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="GPT-5.6 Sol/Terra/Luna support full effort range including none for disabling reasoning."
    ),
    RegistryEntry(
        provider="openai",
        protocol="openai_responses",
        model_family="gpt-5-pro",
        model_patterns=["gpt-5-pro*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning.effort",
        allowed_effort_levels=["high"],
        supported_levels=["high"],
        default_level="high",
        constraints=["only_high_effort_supported"],
        authority_url="https://platform.openai.com/docs/models",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16",
        notes="GPT-5-Pro is fixed to high effort and cannot disable thinking."
    ),
    RegistryEntry(
        provider="openai",
        protocol="openai_responses",
        model_family="gpt-5.1",
        model_patterns=["gpt-5.1*", "gpt-5.2*", "gpt-5-turbo*"],
        model_exclusions=["gpt-5-pro*", "gpt-5.6*"],
        status="legacy",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning.effort",
        allowed_effort_levels=["none", "minimal", "low", "medium", "high"],
        supported_levels=["none", "minimal", "low", "medium", "high"],
        off_strategy="effort_none",
        output_reasoning_paths=["output[type=reasoning].content", "output[type=reasoning].summary"],
        authority_url="https://platform.openai.com/docs/api-reference/responses",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),

    # ------------------------------------------------------------------------
    # OpenAI: Chat Completions API
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="openai",
        protocol="openai_chat",
        model_family="gpt-5.6-chat",
        model_patterns=["gpt-5.6", "gpt-5.6-sol*", "gpt-5.6-terra*", "gpt-5.6-luna*"],
        model_exclusions=["gpt-5-pro*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning_effort",
        allowed_effort_levels=["none", "low", "medium", "high", "xhigh", "max"],
        supported_levels=["none", "low", "medium", "high", "xhigh", "max"],
        default_level="medium",
        off_strategy="effort_none",
        authority_url="https://platform.openai.com/docs/guides/reasoning",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="GPT-5.6 Chat Completions endpoint accepts reasoning_effort='none' to turn off reasoning."
    ),
    RegistryEntry(
        provider="openai",
        protocol="openai_chat",
        model_family="o-series",
        model_patterns=["o1*", "o3*", "o4*"],
        model_exclusions=["o1-preview*", "o1-mini*"],
        status="legacy",
        can_disable=False,  # CANNOT be disabled on Chat Completions
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning_effort",
        allowed_effort_levels=["low", "medium", "high"],
        supported_levels=["low", "medium", "high"],
        constraints=["cannot_disable_on_chat", "temperature_fixed_1_0", "no_penalty_params"],
        output_usage_paths=["usage.completion_tokens_details.reasoning_tokens"],
        authority_url="https://platform.openai.com/docs/guides/reasoning",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="openai",
        protocol="openai_chat",
        model_family="gpt-4o",
        model_patterns=["gpt-4o*", "gpt-4.1*", "gpt-4.5*", "chatgpt-4o*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.UNSUPPORTED],
        control_kind=ControlKind.NONE,
        constraints=["reasoning_params_forbidden_returns_400"],
        authority_url="https://platform.openai.com/docs/models",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),

    # ------------------------------------------------------------------------
    # Anthropic Messages API
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-4.6-adaptive",
        model_patterns=["claude-opus-4-6*", "claude-sonnet-4-6*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ADAPTIVE_SUPPORTED],
        control_kind=ControlKind.ADAPTIVE_EFFORT,
        control_path="thinking.type=adaptive",
        default_when_omitted="off",
        off_strategy="omit_thinking",
        allowed_effort_levels=["low", "medium", "high", "max"],
        supported_levels=["low", "medium", "high", "max"],
        constraints=["omit_thinking_to_disable", "temperature_fixed_1_0_when_enabled"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-4.7-plus",
        model_patterns=["claude-opus-4-7*", "claude-opus-4-8*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ADAPTIVE_SUPPORTED],
        control_kind=ControlKind.ADAPTIVE_EFFORT,
        control_path="thinking.type=adaptive",
        default_when_omitted="off",
        off_strategy="omit_thinking",
        allowed_effort_levels=["low", "medium", "high", "max"],
        supported_levels=["low", "medium", "high", "max"],
        constraints=["omit_thinking_to_disable", "budget_tokens_forbidden_returns_400", "temperature_fixed_1_0_when_enabled"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Claude 4.7+ strictly rejects manual budget_tokens."
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-sonnet-5",
        model_patterns=["claude-sonnet-5*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ADAPTIVE_SUPPORTED],
        control_kind=ControlKind.ADAPTIVE_EFFORT,
        control_path="thinking.type",
        default_when_omitted="on",
        off_strategy="disabled_type",
        disable_payload={"thinking": {"type": "disabled"}},
        allowed_effort_levels=["low", "medium", "high", "max"],
        supported_levels=["low", "medium", "high", "max"],
        constraints=["omit_does_not_disable_must_send_type_disabled", "temperature_fixed_1_0_when_enabled"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Claude Sonnet 5 defaults thinking ON; requires thinking: {type: disabled} to turn off."
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-opus-5",
        model_patterns=["claude-opus-5*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ADAPTIVE_SUPPORTED],
        control_kind=ControlKind.ADAPTIVE_EFFORT,
        control_path="thinking.type",
        default_when_omitted="on",
        off_strategy="disabled_type",
        disable_payload={"thinking": {"type": "disabled"}},
        disable_constraints={"max_effort_when_disabled": "high"},
        allowed_effort_levels=["low", "medium", "high"],
        supported_levels=["low", "medium", "high"],
        constraints=["disabling_only_allowed_when_effort_le_high", "temperature_fixed_1_0_when_enabled"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-fable-mythos",
        model_patterns=["claude-fable-5*", "claude-mythos-5*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.ADAPTIVE_SUPPORTED],
        control_kind=ControlKind.ADAPTIVE_EFFORT,
        control_path="thinking.type=adaptive",
        default_when_omitted="on",
        constraints=["cannot_disable_thinking_always_on"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Fable 5 and Mythos 5 thinking cannot be disabled."
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-manual-legacy",
        model_patterns=["claude-3-5-sonnet*", "claude-3-opus*"],
        status="legacy",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.BUDGET_SUPPORTED],
        control_kind=ControlKind.TOKEN_BUDGET,
        control_path="thinking.budget_tokens",
        off_strategy="omit_thinking",
        min_budget=1024,
        constraints=["budget_tokens_ge_1024", "omit_thinking_to_disable", "temperature_fixed_1_0_when_enabled"],
        output_reasoning_paths=["delta.thinking", "content_block.thinking"],
        authority_url="https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="anthropic",
        protocol="anthropic_messages",
        model_family="claude-retired",
        model_patterns=["claude-3-7-sonnet*"],
        status="deprecated",
        can_disable=False,
        supported_statuses=[ReasoningStatus.UNSUPPORTED],
        control_kind=ControlKind.NONE,
        authority_url="https://docs.anthropic.com/en/docs/about-claude/model-deprecations",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16",
        notes="Claude 3.7 Sonnet retired on 2026-02-19."
    ),

    # ------------------------------------------------------------------------
    # Google Gemini: Generate Content API
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-2.5-flash",
        model_patterns=["gemini-2.5-flash*"],
        model_exclusions=["gemini-2.5-pro*", "gemini-2.5-flash-lite*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.BUDGET_SUPPORTED],
        control_kind=ControlKind.TOKEN_BUDGET,
        control_path="thinkingConfig.thinkingBudget",
        off_strategy="budget_0",
        disable_payload={"thinkingConfig": {"thinkingBudget": 0}},
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16",
        notes="Gemini 2.5 Flash supports thinkingBudget=0 to disable thinking completely."
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-2.5-pro",
        model_patterns=["gemini-2.5-pro*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.BUDGET_SUPPORTED],
        control_kind=ControlKind.TOKEN_BUDGET,
        control_path="thinkingConfig.thinkingBudget",
        constraints=["cannot_disable_budget_0_returns_400"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16",
        notes="Gemini 2.5 Pro reasoning cannot be turned off."
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-2.5-flash-lite",
        model_patterns=["gemini-2.5-flash-lite*"],
        status="active",
        can_disable=True,
        default_when_omitted="off",
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED],
        control_kind=ControlKind.NONE,
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16",
        notes="Gemini 2.5 Flash-Lite thinking is OFF by default."
    ),
    # Gemini 3 Models: explicit supported levels per model, minimal is NOT off
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-3.8-flash",
        model_patterns=["gemini-3.8-flash*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="thinkingConfig.thinkingLevel",
        allowed_effort_levels=["low", "medium", "high"],
        supported_levels=["low", "medium", "high"],
        constraints=["minimal_not_supported_cannot_disable"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-3.7-flash",
        model_patterns=["gemini-3.7-flash*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="thinkingConfig.thinkingLevel",
        allowed_effort_levels=["low", "medium", "high"],
        supported_levels=["low", "medium", "high"],
        constraints=["minimal_not_supported_cannot_disable"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-3.6-flash",
        model_patterns=["gemini-3.6-flash*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="thinkingConfig.thinkingLevel",
        allowed_effort_levels=["minimal", "low", "medium", "high"],
        supported_levels=["minimal", "low", "medium", "high"],
        constraints=["minimal_is_not_off_cannot_disable"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-3.5-flash",
        model_patterns=["gemini-3.5-flash*", "gemini-3.5-flash-lite*", "gemini-3-flash-preview*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="thinkingConfig.thinkingLevel",
        allowed_effort_levels=["minimal", "low", "medium", "high"],
        supported_levels=["minimal", "low", "medium", "high"],
        constraints=["minimal_is_not_off_cannot_disable"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="gemini",
        protocol="gemini_content",
        model_family="gemini-3-pro",
        model_patterns=["gemini-3.1-pro-preview*", "gemini-3-pro-preview*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="thinkingConfig.thinkingLevel",
        allowed_effort_levels=["low", "high"],
        supported_levels=["low", "high"],
        constraints=["cannot_disable"],
        output_reasoning_paths=["candidates[0].content.parts[].thought"],
        authority_url="https://ai.google.dev/gemini-api/docs/thinking",
        authority_scope="exact_model",
        evidence_level="official_exact",
        checked_at="2026-09-16"
    ),

    # ------------------------------------------------------------------------
    # DeepSeek: Chat Completions API
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="deepseek",
        protocol="openai_chat",
        model_family="deepseek-v4",
        model_patterns=["deepseek-flash*", "deepseek-v4-pro*", "deepseek-v4*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ON_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.THINKING_OBJECT,
        control_path="thinking.type",
        off_strategy="disabled_type",
        disable_payload={"thinking": {"type": "disabled"}},
        allowed_effort_levels=["none", "low", "high", "max"],
        supported_levels=["none", "low", "high", "max"],
        constraints=["temperature_penalty_ignored_when_thinking", "top_p_ge_0_95"],
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://api-docs.deepseek.com/guides/thinking_mode/",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="DeepSeek Flash and V4-Pro support thinking: {type: disabled} or reasoning_effort: none."
    ),
    RegistryEntry(
        provider="deepseek",
        protocol="deepseek_responses",
        model_family="deepseek-v4-responses",
        model_patterns=["deepseek-flash*", "deepseek-v4-pro*", "deepseek-v4*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning.effort",
        off_strategy="effort_none",
        allowed_effort_levels=["none", "low", "high", "max"],
        supported_levels=["none", "low", "high", "max"],
        output_reasoning_paths=["output[type=reasoning].content"],
        authority_url="https://api-docs.deepseek.com/guides/thinking_mode/",
        authority_scope="protocol",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),
    RegistryEntry(
        provider="deepseek",
        protocol="openai_chat",
        model_family="deepseek-legacy-reasoner",
        model_patterns=["deepseek-reasoner*", "deepseek-r1*"],
        status="legacy",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ON_SUPPORTED],
        control_kind=ControlKind.THINKING_OBJECT,
        control_path="thinking.type",
        off_strategy="disabled_type",
        disable_payload={"thinking": {"type": "disabled"}},
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://api-docs.deepseek.com/guides/thinking_mode/",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16"
    ),

    # ------------------------------------------------------------------------
    # Alibaba DashScope / Qwen
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="dashscope",
        protocol="openai_chat",
        model_family="qwen3.8",
        model_patterns=["qwen3.8*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED, ReasoningStatus.BUDGET_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning_effort",
        off_strategy="effort_none",
        allowed_effort_levels=["none", "low", "medium", "xhigh"],
        supported_levels=["none", "low", "medium", "xhigh"],
        mutually_exclusive_parameters=[["reasoning_effort", "thinking_budget"]],
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Qwen3.8 supports reasoning_effort ('none','low','medium','xhigh'); mutually exclusive with thinking_budget."
    ),
    RegistryEntry(
        provider="dashscope",
        protocol="dashscope_responses",
        model_family="qwen-responses",
        model_patterns=["qwen*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning.effort",
        off_strategy="effort_none",
        allowed_effort_levels=["none", "low", "medium", "high"],
        supported_levels=["none", "low", "medium", "high"],
        authority_url="https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses",
        authority_scope="protocol",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="DashScope Responses API prioritizes reasoning.effort."
    ),
    RegistryEntry(
        provider="dashscope",
        protocol="openai_chat",
        model_family="qwq-thinking",
        model_patterns=["qwq*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.BUDGET_SUPPORTED],
        control_kind=ControlKind.BOOLEAN,
        control_path="enable_thinking",
        authority_url="https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="QwQ dedicated thinking model; cannot assume disable capability without proof."
    ),

    # ------------------------------------------------------------------------
    # Zhipu AI / Z.AI
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="zhipu",
        protocol="openai_chat",
        model_family="glm-5.3",
        model_patterns=["glm-5.3", "glm-5.3-flash*", "glm-5.3-*"],
        status="active",
        can_disable=False,  # Forced on
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning_effort",
        default_when_omitted="on",
        allowed_effort_levels=["low", "high", "max"],
        supported_levels=["low", "high", "max"],
        default_level="max",
        constraints=["cannot_disable_thinking_forced_on", "type_disabled_returns_400", "top_p_recommended_0_95"],
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://docs.z.ai/guides/overview/migrate-to-glm-new",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="GLM-5.3 and GLM-5.3-Flash mandate thinking (forced on); supports reasoning_effort ('low', 'high', 'max'); setting thinking.type: disabled returns 400."
    ),
    RegistryEntry(
        provider="zhipu",
        protocol="openai_chat",
        model_family="glm-flexible",
        model_patterns=["glm-4.5*", "glm-4.6*", "glm-4.7*", "glm-5", "glm-5.0*", "glm-5.1*", "glm-5.2*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ON_SUPPORTED],
        control_kind=ControlKind.THINKING_OBJECT,
        control_path="thinking.type",
        off_strategy="disabled_type",
        disable_payload={"thinking": {"type": "disabled"}},
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://docs.z.ai/guides/capabilities/thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="GLM-4.5, 4.6, 4.7, 5, 5.1, 5.2 all support thinking: {type: disabled} to turn off."
    ),

    # ------------------------------------------------------------------------
    # Volcengine Ark (Explicit Doubao Models only, ep-* excluded from wildcard)
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="volcengine",
        protocol="openai_chat",
        model_family="doubao-seed",
        model_patterns=["doubao-1.5-pro*", "doubao-seed*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="reasoning_effort",
        off_strategy="effort_none",
        allowed_effort_levels=["none", "minimal", "low", "high"],
        supported_levels=["none", "minimal", "low", "high"],
        constraints=["top_p_ge_0_95_when_thinking"],
        output_reasoning_paths=["choices[0].delta.reasoning_content"],
        authority_url="https://www.volcengine.com/docs/82379/1795150",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Explicit Doubao models support reasoning_effort='none'. ep-* is an endpoint ID, resolved at runtime."
    ),

    # ------------------------------------------------------------------------
    # Ollama Native
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="ollama",
        protocol="ollama_native",
        model_family="ollama-thinking-models",
        model_patterns=["qwen3*", "deepseek-r1*", "deepseek-v3.1*"],
        status="active",
        can_disable=True,
        supported_statuses=[ReasoningStatus.OFF_SUPPORTED, ReasoningStatus.ON_SUPPORTED],
        control_kind=ControlKind.BOOLEAN,
        control_path="think",
        off_strategy="think_false",
        output_reasoning_paths=["message.thinking", "thinking"],
        authority_url="https://docs.ollama.com/capabilities/thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Known Ollama thinking models support think: true/false."
    ),
    RegistryEntry(
        provider="ollama",
        protocol="ollama_native",
        model_family="ollama-gpt-oss",
        model_patterns=["*gpt-oss*"],
        status="active",
        can_disable=False,
        supported_statuses=[ReasoningStatus.FORCED_ON, ReasoningStatus.EFFORT_SUPPORTED],
        control_kind=ControlKind.EFFORT_ENUM,
        control_path="think",
        allowed_effort_levels=["low", "medium", "high"],
        supported_levels=["low", "medium", "high"],
        constraints=["cannot_disable_trace_only_effort"],
        output_reasoning_paths=["message.thinking"],
        authority_url="https://docs.ollama.com/capabilities/thinking",
        authority_scope="model_family",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="GPT-OSS models in Ollama use effort enum and cannot turn off thinking."
    ),
    RegistryEntry(
        provider="ollama",
        protocol="ollama_native",
        model_family="ollama-general",
        model_patterns=["*"],
        model_exclusions=["qwen3*", "deepseek-r1*", "deepseek-v3.1*", "*gpt-oss*"],
        status="conditional",
        can_disable=False,
        supported_statuses=[ReasoningStatus.CONDITIONAL],
        control_kind=ControlKind.NONE,
        authority_url="https://docs.ollama.com/capabilities/thinking",
        authority_scope="provider",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Model-dependent. Conservative default injects no thinking parameter unless probed."
    ),

    # ------------------------------------------------------------------------
    # vLLM OpenAI-compatible
    # ------------------------------------------------------------------------
    RegistryEntry(
        provider="vllm",
        protocol="vllm_chat",
        model_family="vllm-template",
        model_patterns=["*"],
        status="conditional",
        can_disable=False,
        supported_statuses=[ReasoningStatus.CONDITIONAL],
        control_kind=ControlKind.MODEL_TEMPLATE_DEPENDENT,
        control_path="chat_template_kwargs.enable_thinking",
        output_reasoning_paths=["choices[0].delta.reasoning", "choices[0].delta.reasoning_content"],
        authority_url="https://docs.vllm.ai/en/latest/features/reasoning_outputs/",
        authority_scope="provider",
        evidence_level="official_family",
        checked_at="2026-09-16",
        notes="Serving engine template-dependent. Default does not assume global can_disable."
    ),
]


class CapabilityRegistry:
    """Singleton capability registry with disk-backed probe cache and TTL."""

    _instance: Optional["CapabilityRegistry"] = None

    def __init__(self, cache_file: Optional[Path] = None):
        self.entries: List[RegistryEntry] = list(OFFICIAL_REGISTRY)
        self.cache_file = cache_file or (Path(__file__).resolve().parent.parent / "data" / "probe_cache.json")
        self._cache: Dict[str, ProbeCacheEntry] = {}
        self._load_cache()

    @classmethod
    def get_instance(cls) -> "CapabilityRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _make_cache_key(endpoint: str, protocol: str, model: str) -> str:
        clean_ep = endpoint.rstrip("/").lower()
        clean_proto = protocol.strip().lower()
        clean_model = model.strip().lower()
        raw = f"{clean_ep}|{clean_proto}|{clean_model}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _load_cache(self):
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict):
                        self._cache[k] = ProbeCacheEntry.from_dict(v)
        except Exception:
            self._cache = {}

    def _save_cache(self):
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self._cache.items()}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_probe_cache(self, endpoint: str, protocol: str, model: str) -> Optional[ProbeCacheEntry]:
        key = self._make_cache_key(endpoint, protocol, model)
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry
        return None

    def set_probe_cache(
        self,
        endpoint: str,
        protocol: str,
        model: str,
        probe_state: ProbeState,
        effective_kind: ControlKind = ControlKind.NONE,
        details: str = "",
        ttl_seconds: float = 86400.0 * 7
    ):
        key = self._make_cache_key(endpoint, protocol, model)
        entry = ProbeCacheEntry(
            endpoint=endpoint,
            protocol=protocol,
            model=model,
            probe_state=probe_state,
            effective_kind=effective_kind,
            observed_at=time.time(),
            ttl_seconds=ttl_seconds,
            evidence=EvidenceSource.PROBE_CONFIRMED.value if probe_state == ProbeState.CONFIRMED_SUPPORTED else EvidenceSource.PROBE_ACCEPTED.value,
            details=details
        )
        self._cache[key] = entry
        self._save_cache()

    def clear_probe_cache(self, endpoint: str = "", protocol: str = "", model: str = ""):
        if not endpoint and not model:
            self._cache.clear()
        else:
            key = self._make_cache_key(endpoint, protocol, model)
            self._cache.pop(key, None)
        self._save_cache()

    def match(self, provider: str, protocol: str, model: str) -> Optional[RegistryEntry]:
        """Matches an official registry entry using exact/pattern matching.
        
        Evaluates exact provider & protocol matches first.
        """
        provider_clean = (provider or "").strip().lower()
        protocol_clean = (protocol or "").strip().lower()
        model_clean = (model or "").strip()

        # Pass 1: exact provider + protocol match
        for entry in self.entries:
            if entry.provider.lower() == provider_clean and entry.protocol.lower() == protocol_clean:
                if entry.matches_model(model_clean):
                    return entry

        # Pass 2: protocol match (if provider is generic or empty)
        for entry in self.entries:
            if entry.protocol.lower() == protocol_clean:
                if entry.matches_model(model_clean):
                    return entry

        return None

    @staticmethod
    def get_capability_hint(model_name: str) -> Dict[str, Any]:
        """Heuristic name hint.
        
        STRICT RULE: This ONLY returns an exploratory hint.
        It NEVER decides API parameters or overrides official registry/probe entries.
        """
        if not model_name:
            return {"might_support_reasoning": False, "hint_reason": "empty"}

        lower = model_name.lower().strip()
        hints = []
        if any(k in lower for k in ("-r1", "reasoner", "thinking", "reasoning")):
            hints.append("name_contains_reasoning_keyword")
        if any(k in lower for k in ("o1", "o3", "o4")) and not any(k in lower for k in ("gpt-4o", "audio")):
            hints.append("name_contains_o_series")
        if "qwq" in lower:
            hints.append("name_contains_qwq")
        if "flash-thinking" in lower:
            hints.append("name_contains_flash_thinking")

        return {
            "might_support_reasoning": len(hints) > 0,
            "hint_reasons": hints,
            "evidence": EvidenceSource.HEURISTIC_HINT.value
        }


# ============================================================================
# RUNTIME CAPABILITY RESOLVER (6-LEVEL PRIORITY, STRICT V3 RULE)
# ============================================================================

@dataclass
class ResolvedCapability:
    """Resolved model thinking capability decision."""
    can_disable: bool
    can_enable: bool
    forced_on: bool
    control_kind: ControlKind
    evidence_source: EvidenceSource
    details: str = ""
    error_conflict: Optional[str] = None
    registry_entry: Optional[RegistryEntry] = None


class CapabilityResolver:
    """6-Level Priority Capability Resolver.
    
    Priority Hierarchy:
    1. User Manual Override (User Override)
    2. Official Capability Registry
    3. Provider Official Returned Metadata / Capability Metadata
    4. Active Probe Cache
    5. Heuristic Name Hint (exploration only, never decides payload)
    6. Conservative Safe Default (no reasoning parameters injected)
    """

    @classmethod
    def resolve(
        cls,
        provider: str,
        protocol: str,
        model: str,
        endpoint: str = "",
        user_override: Optional[str] = None,  # "on", "off", "auto", None
        provider_metadata: Optional[Dict[str, Any]] = None,
        registry: Optional[CapabilityRegistry] = None
    ) -> ResolvedCapability:
        reg = registry or CapabilityRegistry.get_instance()
        matched_entry = reg.match(provider, protocol, model)

        # 1. Check User Manual Override
        if user_override == "passthrough":
            return ResolvedCapability(
                can_disable=True,
                can_enable=False,
                forced_on=False,
                control_kind=ControlKind.NONE,
                evidence_source=EvidenceSource.USER_OVERRIDE,
                details="用户显式指定不干涉思考模式（原生透传，不向服务端注入任何控制参数）。",
                registry_entry=matched_entry
            )

        if user_override in ("on", "off"):
            # Validate against official registry if known
            if matched_entry:
                if user_override == "off" and not matched_entry.can_disable:
                    if ReasoningStatus.FORCED_ON in matched_entry.supported_statuses or matched_entry.status == "active":
                        return ResolvedCapability(
                            can_disable=False,
                            can_enable=True,
                            forced_on=True,
                            control_kind=matched_entry.control_kind,
                            evidence_source=EvidenceSource.USER_OVERRIDE,
                            details="用户手动要求关闭思考，但模型官方强制要求思考且无法关闭。",
                            error_conflict=f"模型 [{model}] 为强制推理模型，官方不支持关闭思考模式。",
                            registry_entry=matched_entry
                        )
                if user_override == "on" and ReasoningStatus.UNSUPPORTED in matched_entry.supported_statuses:
                    return ResolvedCapability(
                        can_disable=True,
                        can_enable=False,
                        forced_on=False,
                        control_kind=ControlKind.NONE,
                        evidence_source=EvidenceSource.USER_OVERRIDE,
                        details="用户手动要求开启思考，但模型为普通对话模型不支持思考参数。",
                        error_conflict=f"模型 [{model}] 官方明确不支持思考参数，注入参数将返回 400 错误。",
                        registry_entry=matched_entry
                    )
            return ResolvedCapability(
                can_disable=(user_override == "off"),
                can_enable=(user_override == "on"),
                forced_on=False,
                control_kind=matched_entry.control_kind if matched_entry else ControlKind.NONE,
                evidence_source=EvidenceSource.USER_OVERRIDE,
                details=f"用户显式覆盖思考模式为: {user_override}",
                registry_entry=matched_entry
            )

        # 2. Official Capability Registry
        if matched_entry:
            is_forced = (ReasoningStatus.FORCED_ON in matched_entry.supported_statuses)
            is_unsupported = (ReasoningStatus.UNSUPPORTED in matched_entry.supported_statuses)
            return ResolvedCapability(
                can_disable=matched_entry.can_disable,
                can_enable=not is_unsupported,
                forced_on=is_forced,
                control_kind=matched_entry.control_kind,
                evidence_source=EvidenceSource.OFFICIAL_EXACT if matched_entry.evidence_level == "official_exact" else EvidenceSource.OFFICIAL_FAMILY,
                details=f"命中官方注册表家族 [{matched_entry.model_family}]，支持关闭: {matched_entry.can_disable}",
                registry_entry=matched_entry
            )

        # 3. Provider Official Metadata
        if provider_metadata and isinstance(provider_metadata, dict):
            reasoning_supported = provider_metadata.get("reasoning_supported") or provider_metadata.get("supports_thinking")
            if reasoning_supported is not None:
                can_off = bool(provider_metadata.get("can_disable", True))
                return ResolvedCapability(
                    can_disable=can_off,
                    can_enable=bool(reasoning_supported),
                    forced_on=bool(provider_metadata.get("forced_on", False)),
                    control_kind=ControlKind.EFFORT_ENUM if "effort" in str(provider_metadata) else ControlKind.BOOLEAN,
                    evidence_source=EvidenceSource.PROVIDER_METADATA,
                    details="命中 Provider 端点返回的模型能力元数据。"
                )

        # 4. Probe Cache
        cached_probe = reg.get_probe_cache(endpoint, protocol, model)
        if cached_probe:
            if cached_probe.probe_state == ProbeState.CONFIRMED_SUPPORTED:
                return ResolvedCapability(
                    can_disable=True,
                    can_enable=True,
                    forced_on=False,
                    control_kind=cached_probe.effective_kind,
                    evidence_source=EvidenceSource.PROBE_CONFIRMED,
                    details=f"命中已确证的主动探针缓存: {cached_probe.details}"
                )
            elif cached_probe.probe_state == ProbeState.FORCED_ON:
                return ResolvedCapability(
                    can_disable=False,
                    can_enable=True,
                    forced_on=True,
                    control_kind=cached_probe.effective_kind,
                    evidence_source=EvidenceSource.PROBE_CONFIRMED,
                    details=f"命中探针缓存（纯推理模型无法关闭）: {cached_probe.details}"
                )
            elif cached_probe.probe_state in (ProbeState.REJECTED_PARAMETER, ProbeState.UNSUPPORTED):
                return ResolvedCapability(
                    can_disable=True,
                    can_enable=False,
                    forced_on=False,
                    control_kind=ControlKind.NONE,
                    evidence_source=EvidenceSource.PROBE_CONFIRMED,
                    details=f"命中探针缓存（端点拒绝思考参数）: {cached_probe.details}"
                )

        # 5. Heuristic Hint (Only returns hint, does not inject payload)
        hint = reg.get_capability_hint(model)
        if hint.get("might_support_reasoning"):
            return ResolvedCapability(
                can_disable=False,
                can_enable=False,
                forced_on=False,
                control_kind=ControlKind.NONE,
                evidence_source=EvidenceSource.HEURISTIC_HINT,
                details=f"名称启发式提示可能为推理模型 ({hint.get('hint_reasons')})，但在未经主动探针确证前不注入任何参数。"
            )

        # 6. Conservative Safe Default
        return ResolvedCapability(
            can_disable=True,
            can_enable=False,
            forced_on=False,
            control_kind=ControlKind.NONE,
            evidence_source=EvidenceSource.UNKNOWN,
            details="未知模型采用安全保守默认：不向服务端注入任何非标准思考参数。"
        )

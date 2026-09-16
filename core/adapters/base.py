# -*- coding: utf-8 -*-
"""Base ProviderAdapter interface.

Every protocol and provider adapter must implement:
- build_payload: generates provider-compliant request JSON respecting reasoning constraints
- parse_stream_chunk: separates reasoning trace from final translation content
- classify_error: precisely distinguishes thinking parameter 400 errors from auth/quota/404
- probe: executes a provider-specific minimal probe (never universal max_tokens=1)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from core.capability_registry import ControlKind, ProbeState, ReasoningStatus


@dataclass
class ParsedChunk:
    """A parsed streaming chunk separating final translation from thinking trace."""
    content: str = ""
    reasoning: str = ""
    is_done: bool = False
    raw_event: Optional[Dict[str, Any]] = None


@dataclass
class ReasoningErrorClassification:
    """Structured error classification."""
    is_reasoning_parameter_error: bool = False
    offending_parameter: Optional[str] = None
    category: str = "unknown"  # "reasoning_param", "auth", "not_found", "quota", "context_length", "content_filter", "network", "client_error", "server_error"
    message: str = ""
    can_retry_without_reasoning: bool = False


@dataclass
class ProbeResult:
    """Result of an on-demand probe for a model endpoint."""
    state: ProbeState
    control_kind: ControlKind = ControlKind.NONE
    details: str = ""
    latency_ms: int = 0
    raw_status_code: int = 0


class ProviderAdapter(ABC):
    """Abstract base class for protocol-specific LLM adapters."""

    protocol_name: str = "base"

    def __init__(self, provider: str = "", model: str = ""):
        self.provider = provider
        self.model = model

    @abstractmethod
    def get_endpoint_url(self, base_url: str) -> str:
        """Returns the full API endpoint URL given the base_url."""
        pass

    @abstractmethod
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """Returns HTTP headers for the request."""
        pass

    @abstractmethod
    def build_payload(
        self,
        model: str,
        messages: List[Dict[str, str]],
        reasoning_intent: str,  # "off", "on", "auto"
        effort_level: str = "medium",  # "low", "medium", "high", "max"
        budget_tokens: Optional[int] = None,
        temperature: float = 0.3,
        stream: bool = True,
        max_tokens: Optional[int] = None,
        strip_reasoning_param: bool = False
    ) -> Dict[str, Any]:
        """Builds a provider-compliant JSON payload.
        
        If strip_reasoning_param is True, intentionally omits/strips all thinking parameters
        for single-time 400 parameter downgrade retry.
        """
        pass

    @abstractmethod
    def parse_stream_chunk(self, line: str) -> Optional[ParsedChunk]:
        """Parses a single streaming response line.
        
        Extracts content into chunk.content and thinking into chunk.reasoning.
        Never concatenates thinking into content.
        """
        pass

    @abstractmethod
    def classify_error(
        self,
        status_code: int,
        response_body: str,
        headers: Optional[Dict[str, str]] = None
    ) -> ReasoningErrorClassification:
        """Classifies an HTTP error.
        
        Crucial: is_reasoning_parameter_error MUST ONLY be True when the error explicitly
        points to thinking/reasoning/budget/effort/template parameters.
        Auth, quota, 404, context length, and other client/server errors MUST return False.
        """
        pass

    @abstractmethod
    def probe(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 15.0
    ) -> ProbeResult:
        """Executes a provider-specific minimal probe.
        
        Never uses a universal max_tokens=1 across providers.
        Distinguishes confirmed_supported vs accepted_but_unverified vs rejected_parameter.
        """
        pass

"""Model Role Abstraction & Capability Decoupling Engine (CP-30 / CQ-30).

Verifies and enforces:
1. Product decoupling: Roles and capabilities are modeled independently of concrete model identifiers and effort settings.
2. Rejection of invented/unverified model names ("Kein erfundener Modellwert").
3. Rejection of unsupported configurations and effort parameters ("Nicht unterstützte Konfiguration wird abgewiesen").
4. Strict safety: Prohibits automatic login mutations, credential switching, or subscription tier changes.
5. Official grounding: Anchors valid configurations in official provider documentation and schema specifications.
6. Emits structured evidence matching ["official-model-docs", "adapter-schema", "authorized-config"].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class AbstractRole(str, Enum):
    """Product-facing abstract worker roles."""
    PRIMARY_CODER = "PRIMARY_CODER"
    INDEPENDENT_AUDITOR = "INDEPENDENT_AUDITOR"
    FAST_EXPLORER = "FAST_EXPLORER"
    DIFF_REVIEWER = "DIFF_REVIEWER"


class RequiredCapability(str, Enum):
    """Granular task and verification capabilities."""
    CODE_SYNTHESIS = "CODE_SYNTHESIS"
    INDEPENDENT_VERIFICATION = "INDEPENDENT_VERIFICATION"
    LOW_LATENCY = "LOW_LATENCY"
    EXTENDED_REASONING = "EXTENDED_REASONING"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"


class SupportedEffortLevel(str, Enum):
    """Explicitly supported thinking/effort levels."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AuthSurface(str, Enum):
    """Authorized authentication interfaces."""
    GITHUB_ACTIONS_SECRET = "GITHUB_ACTIONS_SECRET"
    LOCAL_ENVIRONMENT_VARIABLE = "LOCAL_ENVIRONMENT_VARIABLE"
    CONFIGURED_KEYSTORE = "CONFIGURED_KEYSTORE"


class UnknownModelError(ValueError):
    """Raised when an unverified or invented model name is submitted."""
    pass


class UnsupportedConfigurationError(ValueError):
    """Raised when unsupported parameters (e.g. invalid effort level or auth mutation) are specified."""
    pass


class MissingCapabilityError(ValueError):
    """Raised when a candidate model lacks the capabilities required by the abstract role."""
    pass


class UnauthorizedAuthMutationError(PermissionError):
    """Raised when an automated configuration attempts to alter login credentials or subscription tiers."""
    pass


@dataclass(frozen=True)
class ModelMetadata:
    """Official grounded model capabilities and specifications."""
    model_id: str
    provider: str
    supported_effort_levels: Set[SupportedEffortLevel]
    supported_capabilities: Set[RequiredCapability]
    official_doc_ref: str
    max_context_window: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "supported_effort_levels": [e.value for e in self.supported_effort_levels],
            "supported_capabilities": [c.value for c in self.supported_capabilities],
            "official_doc_ref": self.official_doc_ref,
            "max_context_window": self.max_context_window,
        }


@dataclass(frozen=True)
class ModelRoleBinding:
    """Authorized concrete binding between an abstract role and a grounded model configuration."""
    role: AbstractRole
    model_id: str
    auth_surface: AuthSurface
    effort_level: SupportedEffortLevel
    is_authorized: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "model_id": self.model_id,
            "auth_surface": self.auth_surface.value,
            "effort_level": self.effort_level.value,
            "is_authorized": self.is_authorized,
        }


class ModelRoleRegistry:
    """Decouples abstract product roles from underlying LLM models and validates against official schemas."""

    ROLE_REQUIRED_CAPABILITIES: Dict[AbstractRole, Set[RequiredCapability]] = {
        AbstractRole.PRIMARY_CODER: {
            RequiredCapability.CODE_SYNTHESIS,
            RequiredCapability.STRUCTURED_OUTPUT,
        },
        AbstractRole.INDEPENDENT_AUDITOR: {
            RequiredCapability.INDEPENDENT_VERIFICATION,
            RequiredCapability.EXTENDED_REASONING,
        },
        AbstractRole.FAST_EXPLORER: {
            RequiredCapability.LOW_LATENCY,
        },
        AbstractRole.DIFF_REVIEWER: {
            RequiredCapability.STRUCTURED_OUTPUT,
            RequiredCapability.INDEPENDENT_VERIFICATION,
        },
    }

    def __init__(self) -> None:
        self.supported_models: Dict[str, ModelMetadata] = {}
        self.role_bindings: Dict[AbstractRole, ModelRoleBinding] = {}
        self._populate_official_models()

    def _populate_official_models(self) -> None:
        """Seeds verified models grounded in official documentation."""
        self.supported_models["gemini-2.5-pro"] = ModelMetadata(
            model_id="gemini-2.5-pro",
            provider="google",
            supported_effort_levels={
                SupportedEffortLevel.NONE,
                SupportedEffortLevel.LOW,
                SupportedEffortLevel.MEDIUM,
                SupportedEffortLevel.HIGH,
            },
            supported_capabilities={
                RequiredCapability.CODE_SYNTHESIS,
                RequiredCapability.INDEPENDENT_VERIFICATION,
                RequiredCapability.EXTENDED_REASONING,
                RequiredCapability.STRUCTURED_OUTPUT,
            },
            official_doc_ref="https://ai.google.dev/gemini-api/docs/models/gemini-v2-5",
            max_context_window=2097152,
        )

        self.supported_models["gemini-2.5-flash"] = ModelMetadata(
            model_id="gemini-2.5-flash",
            provider="google",
            supported_effort_levels={
                SupportedEffortLevel.NONE,
                SupportedEffortLevel.LOW,
            },
            supported_capabilities={
                RequiredCapability.CODE_SYNTHESIS,
                RequiredCapability.LOW_LATENCY,
                RequiredCapability.STRUCTURED_OUTPUT,
            },
            official_doc_ref="https://ai.google.dev/gemini-api/docs/models/gemini-v2-5",
            max_context_window=1048576,
        )

        self.supported_models["gpt-4o"] = ModelMetadata(
            model_id="gpt-4o",
            provider="openai",
            supported_effort_levels={SupportedEffortLevel.NONE},
            supported_capabilities={
                RequiredCapability.CODE_SYNTHESIS,
                RequiredCapability.STRUCTURED_OUTPUT,
                RequiredCapability.INDEPENDENT_VERIFICATION,
            },
            official_doc_ref="https://platform.openai.com/docs/models/gpt-4o",
            max_context_window=128000,
        )

    def bind_role(
        self,
        role: AbstractRole,
        model_id: str,
        auth_surface: AuthSurface,
        effort_level: SupportedEffortLevel = SupportedEffortLevel.NONE,
        request_auth_mutation: bool = False,
        request_subscription_upgrade: bool = False,
    ) -> ModelRoleBinding:
        """Validates and establishes an authorized binding between an abstract role and a concrete model."""
        # Safety invariant: Never allow automatic login mutation or subscription upgrade
        if request_auth_mutation or request_subscription_upgrade:
            raise UnauthorizedAuthMutationError(
                "Automated mutation of login credentials, OAuth scopes, or subscription tiers is forbidden."
            )

        # Invariant: Reject invented or unknown models
        if model_id not in self.supported_models:
            raise UnknownModelError(
                f"Model '{model_id}' is unknown or invented. Must be grounded in official provider docs."
            )

        meta = self.supported_models[model_id]

        # Invariant: Reject unsupported effort levels
        if effort_level not in meta.supported_effort_levels:
            raise UnsupportedConfigurationError(
                f"Effort level '{effort_level.value}' is unsupported by model '{model_id}'. "
                f"Supported: {[e.value for e in meta.supported_effort_levels]}"
            )

        # Invariant: Ensure model possesses all required capabilities for the abstract role
        required = self.ROLE_REQUIRED_CAPABILITIES.get(role, set())
        missing = required - meta.supported_capabilities
        if missing:
            raise MissingCapabilityError(
                f"Model '{model_id}' lacks required capabilities for role '{role.value}': "
                f"{[m.value for m in missing]}"
            )

        binding = ModelRoleBinding(
            role=role,
            model_id=model_id,
            auth_surface=auth_surface,
            effort_level=effort_level,
            is_authorized=True,
        )
        self.role_bindings[role] = binding
        return binding

    def get_role_binding(self, role: AbstractRole) -> Optional[ModelRoleBinding]:
        return self.role_bindings.get(role)

    def generate_model_role_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-30.

        Required fields:
        - 'official-model-docs'
        - 'adapter-schema'
        - 'authorized-config'
        """
        return {
            "official-model-docs": {
                mid: meta.to_dict() for mid, meta in self.supported_models.items()
            },
            "adapter-schema": {
                "roles": [r.value for r in AbstractRole],
                "capabilities": [c.value for c in RequiredCapability],
                "effort_levels": [e.value for e in SupportedEffortLevel],
                "auth_surfaces": [a.value for a in AuthSurface],
                "safety_invariants": {
                    "no_invented_models": True,
                    "unsupported_configs_rejected": True,
                    "no_automatic_login_or_tier_mutations": True,
                },
            },
            "authorized-config": {
                role.value: binding.to_dict() for role, binding in self.role_bindings.items()
            },
        }

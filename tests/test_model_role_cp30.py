"""Tests for CP-30 / CQ-30 / GB-MODEL-ROLE-01: Model Role Abstraction & Capability Decoupling.

Verifies:
1. Abstract roles and capabilities are decoupled from concrete model names and effort settings.
2. Invented or unverified model identifiers are rejected ("Kein erfundener Modellwert").
3. Unsupported effort parameters fail closed ("Nicht unterstützte Konfiguration wird abgewiesen").
4. Models lacking required capabilities for a role are rejected.
5. Automated login alterations or subscription tier mutations are strictly prohibited.
6. Evidence generated with ['official-model-docs', 'adapter-schema', 'authorized-config'].
"""

import pytest

from courier_core.model_role_abstraction import (
    AbstractRole,
    AuthSurface,
    MissingCapabilityError,
    ModelRoleRegistry,
    SupportedEffortLevel,
    UnauthorizedAuthMutationError,
    UnknownModelError,
    UnsupportedConfigurationError,
)


def test_abstract_roles_decoupled_from_concrete_models():
    """Roles are bound to verified grounded models meeting required capability criteria."""
    registry = ModelRoleRegistry()

    binding = registry.bind_role(
        role=AbstractRole.PRIMARY_CODER,
        model_id="gemini-2.5-pro",
        auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
        effort_level=SupportedEffortLevel.MEDIUM,
    )

    assert binding.role == AbstractRole.PRIMARY_CODER
    assert binding.model_id == "gemini-2.5-pro"
    assert binding.effort_level == SupportedEffortLevel.MEDIUM
    assert binding.is_authorized is True


def test_invented_or_unknown_model_rejected():
    """Unverified, hallucinated, or invented model names raise UnknownModelError."""
    registry = ModelRoleRegistry()

    with pytest.raises(UnknownModelError) as exc_info:
        registry.bind_role(
            role=AbstractRole.PRIMARY_CODER,
            model_id="gemini-invented-super-ai",
            auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
        )
    assert "unknown or invented" in str(exc_info.value)


def test_unsupported_effort_level_rejected():
    """Unsupported effort parameters for a model raise UnsupportedConfigurationError."""
    registry = ModelRoleRegistry()

    # gpt-4o does not support HIGH effort parameter in this schema
    with pytest.raises(UnsupportedConfigurationError) as exc_info:
        registry.bind_role(
            role=AbstractRole.DIFF_REVIEWER,
            model_id="gpt-4o",
            auth_surface=AuthSurface.GITHUB_ACTIONS_SECRET,
            effort_level=SupportedEffortLevel.HIGH,
        )
    assert "unsupported by model" in str(exc_info.value)


def test_missing_capability_for_role_rejected():
    """Binding a model that lacks role-required capabilities raises MissingCapabilityError."""
    registry = ModelRoleRegistry()

    # gemini-2.5-flash lacks INDEPENDENT_VERIFICATION and EXTENDED_REASONING needed for INDEPENDENT_AUDITOR
    with pytest.raises(MissingCapabilityError) as exc_info:
        registry.bind_role(
            role=AbstractRole.INDEPENDENT_AUDITOR,
            model_id="gemini-2.5-flash",
            auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
        )
    assert "lacks required capabilities" in str(exc_info.value)


def test_automatic_auth_mutation_or_tier_upgrade_strictly_prohibited():
    """Automated requests to mutate credentials, login sessions, or subscription tiers are blocked."""
    registry = ModelRoleRegistry()

    with pytest.raises(UnauthorizedAuthMutationError) as exc_info:
        registry.bind_role(
            role=AbstractRole.FAST_EXPLORER,
            model_id="gemini-2.5-flash",
            auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
            request_auth_mutation=True,
        )
    assert "Automated mutation of login credentials" in str(exc_info.value)

    with pytest.raises(UnauthorizedAuthMutationError) as exc_info:
        registry.bind_role(
            role=AbstractRole.FAST_EXPLORER,
            model_id="gemini-2.5-flash",
            auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
            request_subscription_upgrade=True,
        )
    assert "subscription tiers is forbidden" in str(exc_info.value)


def test_evidence_generation():
    """Emits required evidence with official-model-docs, adapter-schema, and authorized-config."""
    registry = ModelRoleRegistry()
    registry.bind_role(
        role=AbstractRole.PRIMARY_CODER,
        model_id="gemini-2.5-pro",
        auth_surface=AuthSurface.LOCAL_ENVIRONMENT_VARIABLE,
        effort_level=SupportedEffortLevel.LOW,
    )

    evidence = registry.generate_model_role_evidence()
    required_keys = ["official-model-docs", "adapter-schema", "authorized-config"]
    for k in required_keys:
        assert k in evidence

    assert "gemini-2.5-pro" in evidence["official-model-docs"]
    assert "PRIMARY_CODER" in evidence["authorized-config"]
    assert evidence["adapter-schema"]["safety_invariants"]["no_invented_models"] is True

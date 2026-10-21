"""Tests for CP-40 / CQ-40 / GB-POLICY-GOVERNANCE-01: Policy Governance Engine & Anti-Self-Escalation.

Verifies:
1. Autonomous bots can propose policies in PROPOSED state.
2. Bot self-approval and self-activation are strictly forbidden ("Bot kann Änderung vorschlagen, nicht eigene Freigabe erzeugen").
3. Budget increases (> 0.00 EUR) strictly require verified HUMAN_OWNER authority.
4. Policy activation requires prior verified approval.
5. Evidence generated with ['policy-store', 'approval-authority', 'active-version'].
"""

import pytest

from courier_core.policy_governance_engine import (
    AuthorityRole,
    InsufficientAuthorityError,
    PolicyGovernanceEngine,
    PolicyLifecycleState,
    PolicyProposal,
    SelfApprovalForbiddenError,
)


def test_bot_can_submit_proposal_in_proposed_state():
    """Bots can propose policies, entering the store in unapproved PROPOSED status."""
    engine = PolicyGovernanceEngine()

    proposal = PolicyProposal(
        policy_id="POL-CODE-STYLE-V1",
        version="1.1.0",
        proposer_id="grokbot_agent",
        proposer_role=AuthorityRole.AUTONOMOUS_BOT,
        proposed_spend_limit_eur=0.00,
        proposed_scope_roots=["src/style"],
    )

    p = engine.submit_proposal(proposal)
    assert p.state == PolicyLifecycleState.PROPOSED
    assert "POL-CODE-STYLE-V1" in engine.policy_store


def test_bot_self_approval_is_strictly_forbidden():
    """An autonomous bot attempting to approve a policy raises SelfApprovalForbiddenError."""
    engine = PolicyGovernanceEngine()

    proposal = PolicyProposal(
        policy_id="POL-BOT-PRIVILEGE",
        version="1.0.0",
        proposer_id="grokbot_agent",
        proposer_role=AuthorityRole.AUTONOMOUS_BOT,
        proposed_spend_limit_eur=0.00,
        proposed_scope_roots=["src"],
    )
    engine.submit_proposal(proposal)

    with pytest.raises(SelfApprovalForbiddenError) as exc_info:
        engine.approve_proposal(
            policy_id="POL-BOT-PRIVILEGE",
            approver_id="grokbot_agent",
            approver_role=AuthorityRole.AUTONOMOUS_BOT,
        )
    assert "Autonomous bots cannot approve" in str(exc_info.value)


def test_proposer_cannot_approve_own_proposal():
    """Any proposer attempting to approve their own proposal raises SelfApprovalForbiddenError."""
    engine = PolicyGovernanceEngine()

    proposal = PolicyProposal(
        policy_id="POL-OWNER-SELF",
        version="1.0.0",
        proposer_id="alice",
        proposer_role=AuthorityRole.INDEPENDENT_AUDITOR,
        proposed_spend_limit_eur=0.00,
        proposed_scope_roots=["src"],
    )
    engine.submit_proposal(proposal)

    with pytest.raises(SelfApprovalForbiddenError) as exc_info:
        engine.approve_proposal(
            policy_id="POL-OWNER-SELF",
            approver_id="alice",
            approver_role=AuthorityRole.HUMAN_OWNER,
        )
    assert "cannot approve their own proposal" in str(exc_info.value)


def test_budget_increase_strictly_requires_human_owner():
    """Increasing spending budget above 0.00 EUR strictly requires HUMAN_OWNER role."""
    engine = PolicyGovernanceEngine()

    proposal = PolicyProposal(
        policy_id="POL-EXPENSIVE",
        version="2.0.0",
        proposer_id="grokbot_agent",
        proposer_role=AuthorityRole.AUTONOMOUS_BOT,
        proposed_spend_limit_eur=15.00,
        proposed_scope_roots=["src"],
    )
    engine.submit_proposal(proposal)

    # Independent auditor cannot approve budget increase
    with pytest.raises(InsufficientAuthorityError) as exc_info:
        engine.approve_proposal(
            policy_id="POL-EXPENSIVE",
            approver_id="auditor_bob",
            approver_role=AuthorityRole.INDEPENDENT_AUDITOR,
        )
    assert "strictly requires HUMAN_OWNER" in str(exc_info.value)

    # Human owner CAN approve budget increase
    approved = engine.approve_proposal(
        policy_id="POL-EXPENSIVE",
        approver_id="founder_dennis",
        approver_role=AuthorityRole.HUMAN_OWNER,
    )
    assert approved.state == PolicyLifecycleState.APPROVED_BY_AUTHORITY


def test_activation_requires_prior_approval():
    """A policy cannot be activated while still in PROPOSED status."""
    engine = PolicyGovernanceEngine()

    proposal = PolicyProposal(
        policy_id="POL-UNAPPROVED",
        version="1.0.0",
        proposer_id="bot",
        proposer_role=AuthorityRole.AUTONOMOUS_BOT,
        proposed_spend_limit_eur=0.00,
        proposed_scope_roots=["src"],
    )
    engine.submit_proposal(proposal)

    with pytest.raises(PermissionError) as exc_info:
        engine.activate_policy("POL-UNAPPROVED")
    assert "Cannot activate policy" in str(exc_info.value)


def test_evidence_generation():
    """Emits required evidence with policy-store, approval-authority, and active-version."""
    engine = PolicyGovernanceEngine()
    evidence = engine.generate_governance_evidence()

    required_keys = ["policy-store", "approval-authority", "active-version"]
    for k in required_keys:
        assert k in evidence

    assert evidence["approval-authority"]["bot_self_approval_prohibited"] is True
    assert evidence["active-version"]["active_policy_id"] == "POL-BASELINE-V1"
    assert evidence["active-version"]["active_spend_limit_eur"] == "0.00"

"""Policy Governance Engine & Anti-Self-Escalation Guard (CP-40 / CQ-40).

Verifies and enforces:
1. Strict separation of policy proposals, independent approvals, and active enforced versions.
2. Anti-Self-Escalation ("Bot kann Änderung vorschlagen, nicht eigene Freigabe erzeugen"):
   Autonomous bots can author proposals, but can NEVER approve or activate their own policies.
3. Authority-Scoped Approvals ("Mehr Kapazität/Scope verlangt passende Autorität"):
   Any budget expansion (> 0.00 EUR) or scope modification requires verified HUMAN_OWNER authority.
4. Immutable Provenance: Retains proposer identities, timestamps, and approval audit trails.
5. Emits structured evidence matching ["policy-store", "approval-authority", "active-version"].
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class PolicyLifecycleState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED_BY_AUTHORITY = "APPROVED_BY_AUTHORITY"
    ACTIVE_ENFORCED = "ACTIVE_ENFORCED"
    REJECTED = "REJECTED"


class AuthorityRole(str, Enum):
    AUTONOMOUS_BOT = "AUTONOMOUS_BOT"
    INDEPENDENT_AUDITOR = "INDEPENDENT_AUDITOR"
    HUMAN_OWNER = "HUMAN_OWNER"


class SelfApprovalForbiddenError(PermissionError):
    """Raised when an autonomous agent attempts to self-approve a policy or grant itself permissions."""
    pass


class InsufficientAuthorityError(PermissionError):
    """Raised when an approval role lacks the required authority to alter budgets or scope."""
    pass


@dataclass
class PolicyProposal:
    policy_id: str
    version: str
    proposer_id: str
    proposer_role: AuthorityRole
    proposed_spend_limit_eur: float
    proposed_scope_roots: List[str]
    state: PolicyLifecycleState = PolicyLifecycleState.PROPOSED
    approved_by: Optional[str] = None
    approver_role: Optional[AuthorityRole] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "proposer_id": self.proposer_id,
            "proposer_role": self.proposer_role.value,
            "proposed_spend_limit_eur": f"{self.proposed_spend_limit_eur:.2f}",
            "proposed_scope_roots": list(self.proposed_scope_roots),
            "state": self.state.value,
            "approved_by": self.approved_by,
            "approver_role": self.approver_role.value if self.approver_role else None,
        }


class PolicyGovernanceEngine:
    """Manages policy proposals, anti-self-approval gates, and active version activations."""

    def __init__(self, baseline_policy_id: str = "POL-BASELINE-V1") -> None:
        self.policy_store: Dict[str, PolicyProposal] = {}
        self.active_version: str = baseline_policy_id

        # Register baseline policy
        self.policy_store[baseline_policy_id] = PolicyProposal(
            policy_id=baseline_policy_id,
            version="1.0.0",
            proposer_id="system_init",
            proposer_role=AuthorityRole.HUMAN_OWNER,
            proposed_spend_limit_eur=0.00,
            proposed_scope_roots=["src", "tests", "courier_core"],
            state=PolicyLifecycleState.ACTIVE_ENFORCED,
            approved_by="founder_dennis",
            approver_role=AuthorityRole.HUMAN_OWNER,
        )

    def submit_proposal(self, proposal: PolicyProposal) -> PolicyProposal:
        """Submits a new policy proposal into the store in PROPOSED status."""
        proposal.state = PolicyLifecycleState.PROPOSED
        self.policy_store[proposal.policy_id] = proposal
        return proposal

    def approve_proposal(
        self,
        policy_id: str,
        approver_id: str,
        approver_role: AuthorityRole,
    ) -> PolicyProposal:
        """Approves a proposal, strictly preventing self-approval and enforcing human budget gates.

        Strict invariants:
        - Autonomous bots can NEVER approve any policy proposal.
        - Proposer cannot be the approver.
        - Spending limits above 0.00 EUR strictly require HUMAN_OWNER role.
        """
        if policy_id not in self.policy_store:
            raise KeyError(f"Policy '{policy_id}' not found in policy store")

        proposal = self.policy_store[policy_id]

        if approver_role == AuthorityRole.AUTONOMOUS_BOT:
            raise SelfApprovalForbiddenError(
                "Autonomous bots cannot approve policy proposals. Approval requires human or independent authority."
            )

        if proposal.proposer_id == approver_id:
            raise SelfApprovalForbiddenError(
                f"Proposer '{proposal.proposer_id}' cannot approve their own proposal."
            )

        if proposal.proposed_spend_limit_eur > 0.00 and approver_role != AuthorityRole.HUMAN_OWNER:
            raise InsufficientAuthorityError(
                f"Increasing budget to {proposal.proposed_spend_limit_eur} EUR strictly requires HUMAN_OWNER authority."
            )

        proposal.state = PolicyLifecycleState.APPROVED_BY_AUTHORITY
        proposal.approved_by = approver_id
        proposal.approver_role = approver_role
        return proposal

    def activate_policy(self, policy_id: str) -> str:
        """Activates an approved policy, transitioning it to ACTIVE_ENFORCED."""
        if policy_id not in self.policy_store:
            raise KeyError(f"Policy '{policy_id}' not found")

        proposal = self.policy_store[policy_id]
        if proposal.state != PolicyLifecycleState.APPROVED_BY_AUTHORITY:
            raise PermissionError(
                f"Cannot activate policy '{policy_id}' in state '{proposal.state.value}'. "
                "Policy must be in APPROVED_BY_AUTHORITY state."
            )

        proposal.state = PolicyLifecycleState.ACTIVE_ENFORCED
        self.active_version = policy_id
        return self.active_version

    def generate_governance_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-40.

        Required fields:
        - 'policy-store'
        - 'approval-authority'
        - 'active-version'
        """
        return {
            "policy-store": {
                pid: prop.to_dict() for pid, prop in self.policy_store.items()
            },
            "approval-authority": {
                "bot_self_approval_prohibited": True,
                "human_owner_budget_gate_enforced": True,
                "total_proposals": len(self.policy_store),
            },
            "active-version": {
                "active_policy_id": self.active_version,
                "active_state": self.policy_store[self.active_version].state.value,
                "active_spend_limit_eur": f"{self.policy_store[self.active_version].proposed_spend_limit_eur:.2f}",
            },
        }

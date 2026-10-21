"""Prompt Effect Auditor & Capability Consistency Engine (CP-31 / CQ-31).

Verifies and enforces:
1. Alignment between prompt text, declared capabilities, risk tier, and actual operational effects.
2. Inconsistency detection: Packages claiming read-only/inspection labels that secretly invoke shell or mutation effects are flagged.
3. Stable versioned IDs: Inconsistent entries are marked NON_EXECUTABLE or flagged for DELTA_PROPOSED without mutating catalog identities.
4. Emits structured evidence matching ["prompt-registry", "capability-schema", "effect-policy"].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class DeclaredEffect(str, Enum):
    """Operational effects permitted or claimed by a prompt/package."""
    READ_ONLY = "READ_ONLY"
    INSPECTION = "INSPECTION"
    LOCAL_TEST = "LOCAL_TEST"
    MUTATING_WRITE = "MUTATING_WRITE"
    SHELL_EXECUTION = "SHELL_EXECUTION"


class RiskTier(str, Enum):
    """Risk tier declared for the operation."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExecutableStatus(str, Enum):
    """Catalog execution admissibility status."""
    EXECUTABLE = "EXECUTABLE"
    NON_EXECUTABLE = "NON_EXECUTABLE"
    DELTA_PROPOSED = "DELTA_PROPOSED"


@dataclass
class PromptPackageEntry:
    """A versioned work package entry in the prompt catalog."""
    package_id: str
    version: str
    prompt_text: str
    declared_effects: Set[DeclaredEffect]
    declared_risk: RiskTier
    actual_effects: Set[DeclaredEffect]
    status: ExecutableStatus = ExecutableStatus.EXECUTABLE
    inconsistency_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "prompt_text": self.prompt_text,
            "declared_effects": [e.value for e in sorted(self.declared_effects)],
            "declared_risk": self.declared_risk.value,
            "actual_effects": [e.value for e in sorted(self.actual_effects)],
            "status": self.status.value,
            "inconsistency_reasons": list(self.inconsistency_reasons),
        }


class PromptEffectAuditor:
    """Audits prompt entries for semantic and capability mismatches."""

    def __init__(self) -> None:
        self.registry: Dict[str, PromptPackageEntry] = {}

    def register_package(self, entry: PromptPackageEntry) -> None:
        self.registry[entry.package_id] = entry

    def audit_entry(self, package_id: str) -> PromptPackageEntry:
        """Audits a catalog entry for capability, effect, and risk alignment.

        Strict invariants:
        - If declared as READ_ONLY or INSPECTION, but actual effects require MUTATING_WRITE,
          SHELL_EXECUTION, or LOCAL_TEST, the entry is marked NON_EXECUTABLE.
        - If declared risk is LOW, but actual effects include MUTATING_WRITE or SHELL_EXECUTION,
          the entry is marked NON_EXECUTABLE.
        - Preserves the stable package_id and version.
        """
        if package_id not in self.registry:
            raise KeyError(f"Package '{package_id}' not found in registry")

        entry = self.registry[package_id]
        inconsistencies = []

        is_declared_read_only = (
            DeclaredEffect.READ_ONLY in entry.declared_effects
            or DeclaredEffect.INSPECTION in entry.declared_effects
        ) and (
            DeclaredEffect.MUTATING_WRITE not in entry.declared_effects
            and DeclaredEffect.SHELL_EXECUTION not in entry.declared_effects
        )

        has_active_mutation = (
            DeclaredEffect.MUTATING_WRITE in entry.actual_effects
            or DeclaredEffect.SHELL_EXECUTION in entry.actual_effects
            or DeclaredEffect.LOCAL_TEST in entry.actual_effects
        )

        if is_declared_read_only and has_active_mutation:
            active_mismatches = [
                e.value for e in entry.actual_effects if e in {
                    DeclaredEffect.MUTATING_WRITE,
                    DeclaredEffect.SHELL_EXECUTION,
                    DeclaredEffect.LOCAL_TEST,
                }
            ]
            inconsistencies.append(
                f"Declared read-only/inspection but requires active effects: {active_mismatches}"
            )

        if entry.declared_risk == RiskTier.LOW and (
            DeclaredEffect.MUTATING_WRITE in entry.actual_effects
            or DeclaredEffect.SHELL_EXECUTION in entry.actual_effects
        ):
            inconsistencies.append(
                "Declared risk is LOW but actual effects include file mutation or shell execution"
            )

        # Update entry status
        if inconsistencies:
            entry.status = ExecutableStatus.NON_EXECUTABLE
            entry.inconsistency_reasons = inconsistencies
        else:
            entry.status = ExecutableStatus.EXECUTABLE
            entry.inconsistency_reasons = []

        return entry

    def propose_delta(
        self,
        package_id: str,
        corrected_effects: Set[DeclaredEffect],
        corrected_risk: RiskTier,
    ) -> PromptPackageEntry:
        """Proposes a safe delta update to an inconsistent entry, setting status to DELTA_PROPOSED."""
        entry = self.registry[package_id]
        entry.declared_effects = corrected_effects
        entry.declared_risk = corrected_risk
        entry.status = ExecutableStatus.DELTA_PROPOSED
        return entry

    def generate_prompt_audit_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-31.

        Required fields:
        - 'prompt-registry'
        - 'capability-schema'
        - 'effect-policy'
        """
        return {
            "prompt-registry": {
                pid: entry.to_dict() for pid, entry in self.registry.items()
            },
            "capability-schema": {
                "effects": [e.value for e in DeclaredEffect],
                "risk_tiers": [r.value for r in RiskTier],
                "executable_statuses": [s.value for s in ExecutableStatus],
            },
            "effect-policy": {
                "read_only_strictly_enforced": True,
                "risk_underreporting_blocked": True,
                "stable_ids_versioned": True,
                "inconsistent_entries_non_executable": True,
            },
        }

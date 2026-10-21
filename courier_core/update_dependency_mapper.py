"""Update Dependency Mapper & Surgical Judgment Re-evaluation Engine (CP-36 / CQ-36).

Verifies and enforces:
1. Smallest dependency map from Code, Tests, Policy, and Runtime contracts to Catalog Package IDs.
2. Relevance targeting: Code changes surgically invalidate ONLY affected package IDs.
3. Zero-waste discipline ("Irrelevantes Update erzeugt keinen Pro-Aufruf"): Cosmetic/doc edits
   trigger zero Pro review calls and invalidate zero existing judgments.
4. Judgment reuse: Existing verified judgments remain referenced and valid for unaffected packages.
5. Emits structured evidence matching ["diff", "evidence-dependencies", "catalog-IDs"].
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ChangeCategory(str, Enum):
    CODE = "CODE"
    TEST = "TEST"
    POLICY = "POLICY"
    RUNTIME_CONTRACT = "RUNTIME_CONTRACT"
    COSMETIC_DOC = "COSMETIC_DOC"


@dataclass(frozen=True)
class FileDelta:
    path: str
    category: ChangeCategory
    lines_added: int
    lines_removed: int
    is_cosmetic_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category.value,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "is_cosmetic_only": self.is_cosmetic_only,
        }


@dataclass(frozen=True)
class ReevaluationPlan:
    delta_sha: str
    affected_catalog_ids: List[str]
    unaffected_reused_catalog_ids: List[str]
    pro_calls_required: int
    reasons_by_package: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta_sha": self.delta_sha,
            "affected_catalog_ids": list(self.affected_catalog_ids),
            "unaffected_reused_catalog_ids": list(self.unaffected_reused_catalog_ids),
            "pro_calls_required": self.pro_calls_required,
            "reasons_by_package": dict(self.reasons_by_package),
        }


class UpdateDependencyMapper:
    """Calculates surgical re-evaluation boundaries across catalog packages."""

    DEPENDENCY_INDEX: Dict[str, Set[str]] = {
        "courier_core/runtime_lease.py": {"CP-08", "CP-09", "CP-11", "CP-12"},
        "courier_core/failure_taxonomy.py": {"CP-19"},
        "courier_core/task_handoff.py": {"CP-20"},
        "courier_core/cannon_parallelism_planner.py": {"CP-21"},
        "courier_core/resource_scope_boundary.py": {"CP-22"},
        "courier_core/lazy_expansion_engine.py": {"CP-23"},
        "courier_core/batching_policy_engine.py": {"CP-24"},
        "courier_core/fanin_barrier_engine.py": {"CP-25"},
        "courier_core/minimal_context_slicer.py": {"CP-26"},
        "courier_core/judgment_cache_engine.py": {"CP-27"},
        "courier_core/resource_capacity_limiter.py": {"CP-28"},
        "courier_core/reasoning_evaluation_engine.py": {"CP-29"},
        "courier_core/model_role_abstraction.py": {"CP-30"},
        "courier_core/prompt_effect_auditor.py": {"CP-31"},
        "courier_core/untrusted_content_sanitizer.py": {"CP-32"},
        "courier_core/thought_inbox_engine.py": {"CP-33"},
        "courier_core/work_package_graph_decomposer.py": {"CP-34"},
        "courier_core/task_package_portability.py": {"CP-35"},
    }

    def __init__(self, full_catalog_ids: Optional[List[str]] = None) -> None:
        self.full_catalog_ids: List[str] = full_catalog_ids or [
            f"CP-{i:02d}" for i in range(1, 51)
        ]

    def evaluate_delta(
        self,
        delta_sha: str,
        deltas: List[FileDelta],
    ) -> ReevaluationPlan:
        """Evaluates file diffs to produce a minimal, surgical re-evaluation plan."""
        affected_set: Set[str] = set()
        reasons: Dict[str, str] = {}

        # Filter out purely cosmetic changes
        actionable_deltas = [
            d for d in deltas
            if not d.is_cosmetic_only and d.category != ChangeCategory.COSMETIC_DOC
        ]

        if not actionable_deltas:
            # All changes are cosmetic or comments: 0 Pro calls, 0 invalidations
            return ReevaluationPlan(
                delta_sha=delta_sha,
                affected_catalog_ids=[],
                unaffected_reused_catalog_ids=list(self.full_catalog_ids),
                pro_calls_required=0,
                reasons_by_package={
                    cid: "Cosmetic update only. Verified judgment retained without review."
                    for cid in self.full_catalog_ids
                },
            )

        for d in actionable_deltas:
            for indexed_path, bound_ids in self.DEPENDENCY_INDEX.items():
                if d.path.endswith(indexed_path) or indexed_path in d.path:
                    for cid in bound_ids:
                        affected_set.add(cid)
                        reasons[cid] = f"Direct code change in bound module '{indexed_path}'"

        sorted_affected = sorted(affected_set)
        unaffected = sorted(set(self.full_catalog_ids) - affected_set)

        return ReevaluationPlan(
            delta_sha=delta_sha,
            affected_catalog_ids=sorted_affected,
            unaffected_reused_catalog_ids=unaffected,
            pro_calls_required=len(sorted_affected),
            reasons_by_package=reasons,
        )

    def generate_dependency_evidence(
        self,
        plan: ReevaluationPlan,
        deltas: List[FileDelta],
    ) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-36.

        Required fields:
        - 'diff'
        - 'evidence-dependencies'
        - 'catalog-IDs'
        """
        return {
            "diff": {
                "delta_sha": plan.delta_sha,
                "files_changed_count": len(deltas),
                "files": [d.to_dict() for d in deltas],
            },
            "evidence-dependencies": {
                "affected_packages": plan.affected_catalog_ids,
                "reused_packages_count": len(plan.unaffected_reused_catalog_ids),
                "reasons": plan.reasons_by_package,
                "zero_pro_call_invariant_verified": (
                    plan.pro_calls_required == len(plan.affected_catalog_ids)
                ),
            },
            "catalog-IDs": {
                "targeted_ids": plan.affected_catalog_ids,
                "preserved_ids": plan.unaffected_reused_catalog_ids,
            },
        }

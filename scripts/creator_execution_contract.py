#!/usr/bin/env python3
"""Creator Factory Bounded Execution Contract.

Validates WorkPlans against strict safety invariants, concurrency fences,
dependency preconditions, and zero-spend constraints before allowing execution.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.autonomous_continuation_policy import (
    STRICTLY_PROHIBITED_ACTIONS,
)
from scripts.creator_work_planner import (
    PLAN_SCHEMA_VERSION,
    ExecutionClass,
    RiskClass,
    WorkPlan,
)
from scripts.creator_work_queue import (
    validate_finite_exact_zero,
)

HEAVY_JOB_LIMIT = 1


@dataclass(frozen=True)
class ContractValidationResult:
    """Deterministic result of execution contract verification."""

    valid: bool
    code: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreatorExecutionContract:
    """Enforces execution preconditions on WorkPlans."""

    @classmethod
    def validate_plan_for_execution(
        cls,
        plan: WorkPlan,
        current_asset_state_hash: str | None = None,
        active_task_ids: set[str] | None = None,
        current_heavy_jobs_running: int = 0,
        repo_dir: Path | None = None,
    ) -> ContractValidationResult:
        """Run complete 14-point deterministic validation on a WorkPlan."""
        # 1. Schema version
        if plan.plan_schema_version != PLAN_SCHEMA_VERSION:
            return ContractValidationResult(
                valid=False,
                code="INVALID_PLAN_SCHEMA",
                message=f"Plan schema {plan.plan_schema_version} unsupported (expected {PLAN_SCHEMA_VERSION})",
                details={"plan_schema": plan.plan_schema_version},
            )

        # 2. Identifiers
        if not plan.plan_id or not plan.task_id or not plan.content_id:
            return ContractValidationResult(
                valid=False,
                code="IDENTIFIERS_MISSING",
                message="Plan ID, Task ID, or Content ID is missing or empty",
                details={"plan_id": plan.plan_id, "task_id": plan.task_id, "content_id": plan.content_id},
            )

        # 3. State hash currency
        if current_asset_state_hash is not None and current_asset_state_hash != plan.source_state_hash:
            return ContractValidationResult(
                valid=False,
                code="STATE_HASH_MISMATCH",
                message="Current asset state hash does not match plan source state hash (stale plan)",
                details={"current": current_asset_state_hash, "plan": plan.source_state_hash},
            )

        # 4. Duplicate active task check
        active_ids = active_task_ids or set()
        if plan.task_id in active_ids:
            return ContractValidationResult(
                valid=False,
                code="DUPLICATE_ACTIVE_TASK",
                message=f"Task {plan.task_id} is already active; duplicate execution prohibited",
                details={"task_id": plan.task_id},
            )

        # 5. Strict Zero-Spend Money Firewall
        ok_money, money_code = validate_finite_exact_zero(plan.money_limit_eur)
        if not ok_money:
            return ContractValidationResult(
                valid=False,
                code="MONEY_GATE_VIOLATION",
                message="Money limit is not strictly numeric finite exact zero",
                details={"money_limit_eur": plan.money_limit_eur, "code": money_code},
            )

        # 6. Action Class / Prohibited Operations
        if plan.action_type in STRICTLY_PROHIBITED_ACTIONS:
            return ContractValidationResult(
                valid=False,
                code="PROHIBITED_ACTION",
                message=f"Action {plan.action_type} is strictly prohibited from autonomous execution",
                details={"action_type": plan.action_type},
            )

        if plan.execution_class == ExecutionClass.UNKNOWN.value or plan.risk_class == RiskClass.UNKNOWN.value:
            return ContractValidationResult(
                valid=False,
                code="UNKNOWN_EXECUTION_OR_RISK_CLASS",
                message="Execution class or risk class is UNKNOWN (fail-closed)",
                details={"execution_class": plan.execution_class, "risk_class": plan.risk_class},
            )

        # 7. Iteration limit check
        if plan.maximum_iterations != 1:
            return ContractValidationResult(
                valid=False,
                code="INVALID_ITERATION_LIMIT",
                message=f"Maximum iterations must be exactly 1 (got {plan.maximum_iterations})",
                details={"maximum_iterations": plan.maximum_iterations},
            )

        # 8. Call limits
        if plan.maximum_model_calls < 0 or plan.maximum_external_calls < 0:
            return ContractValidationResult(
                valid=False,
                code="INVALID_CALL_LIMITS",
                message="Call limits must be non-negative",
                details={"model_calls": plan.maximum_model_calls, "external_calls": plan.maximum_external_calls},
            )

        if plan.maximum_external_calls > 0:
            return ContractValidationResult(
                valid=False,
                code="EXTERNAL_CALLS_PROHIBITED",
                message="Autonomous Creator Factory execution forbids external calls",
                details={"maximum_external_calls": plan.maximum_external_calls},
            )

        # 9. Gate Bypass Protection
        if plan.blocking_gate in {"AUDIENCE_DECISION_GATE", "PUBLICATION_APPROVAL_GATE"}:
            if plan.execution_class != ExecutionClass.HUMAN_GATE.value:
                return ContractValidationResult(
                    valid=False,
                    code="PROHIBITED_GATE_BYPASS",
                    message=f"Cannot execute non-human work when blocked by {plan.blocking_gate}",
                    details={"blocking_gate": plan.blocking_gate, "execution_class": plan.execution_class},
                )

        # 10. Heavy job limit
        if plan.requires_model and current_heavy_jobs_running >= HEAVY_JOB_LIMIT:
            return ContractValidationResult(
                valid=False,
                code="HEAVY_JOB_LIMIT_EXCEEDED",
                message=f"Heavy job limit reached ({current_heavy_jobs_running}/{HEAVY_JOB_LIMIT})",
                details={"current_heavy_jobs": current_heavy_jobs_running, "limit": HEAVY_JOB_LIMIT},
            )

        # 11. Dependencies satisfaction check
        if repo_dir and plan.dependencies:
            for dep in plan.dependencies:
                dep_path = Path(dep)
                abs_dep = dep_path if dep_path.is_absolute() else (repo_dir / dep_path)
                if not abs_dep.exists():
                    return ContractValidationResult(
                        valid=False,
                        code="DEPENDENCY_MISSING",
                        message=f"Required dependency not found: {dep}",
                        details={"missing_dependency": dep},
                    )

        # All checks passed
        return ContractValidationResult(
            valid=True,
            code="PLAN_VALID_FOR_EXECUTION",
            message="WorkPlan satisfies all safety invariants and execution preconditions",
            details={"plan_id": plan.plan_id, "task_id": plan.task_id},
        )

#!/usr/bin/env python3
"""Creator Factory Autonomous Work Planner.

Generates deterministic, zero-cost, bounded WorkPlans from Creator Asset Inventory
and Ready-Work Queue items while preventing duplicate operations and enforcing
strict safety invariants.
"""

from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.creator_asset_inventory import (
    CreatorAssetInventory,
    CreatorAssetRecord,
)
from scripts.creator_work_queue import (
    CreatorWorkQueue,
    CreatorWorkQueueItem,
    QueueItemStatus,
    validate_finite_exact_zero,
)

PLAN_SCHEMA_VERSION = "1.0"


class RiskClass(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class ExecutionClass(str, enum.Enum):
    DETERMINISTIC_LOCAL = "DETERMINISTIC_LOCAL"
    MODEL_BUILD = "MODEL_BUILD"
    MODEL_REVIEW = "MODEL_REVIEW"
    EXTERNAL_READ = "EXTERNAL_READ"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    HUMAN_GATE = "HUMAN_GATE"
    NO_ACTION = "NO_ACTION"
    UNKNOWN = "UNKNOWN"


class PlanStatus(str, enum.Enum):
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_REVIEW = "WAITING_REVIEW"
    NO_USEFUL_NEW_WORK = "NO_USEFUL_NEW_WORK"
    DUPLICATE_ACTIVE_TASK = "DUPLICATE_ACTIVE_TASK"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    UNKNOWN = "UNKNOWN"


# Operations that inherently cross security, money, or publication boundaries
HIGH_RISK_ACTIONS = {
    "REAL_YOUTUBE_UPLOAD",
    "PUBLIC_RELEASE",
    "SET_PUBLICATION_AUTHORIZED_TRUE",
    "CREATE_REAL_APPROVAL_RECORD",
    "SPEND_MONEY",
    "SUBSCRIPTION_OR_CREDIT_CHANGE",
    "EXTERNAL_DESTRUCTIVE_OPERATIONS",
    "IDENTITY_OR_KYC_DECLARATIONS",
    "AUDIENCE_CLASSIFICATION",
}

MEDIUM_RISK_ACTIONS = {
    "PACKAGE_PREPARATION",
    "METADATA_LINTING",
    "PROPOSAL_PREPARATION",
    "HUMAN_PUBLICATION_APPROVAL",
}

LOW_RISK_ACTIONS = {
    "LOCAL_QC_EXECUTION",
    "ASSET_VALIDATION",
    "PREVIEW_GENERATION",
    "INVENTORY_REFRESH",
    "QUEUE_DEDUPLICATION",
    "PACKAGING_VERIFICATION",
    "SOURCE_DISCOVERY",
    "IDLE_NO_ACTION",
}


@dataclass(frozen=True)
class WorkPlan:
    """Deterministic, bounded execution plan for a single creator task."""

    plan_id: str
    plan_schema_version: str
    source_state_hash: str
    created_from_queue_hash: str
    content_id: str
    task_id: str
    action_type: str
    status: str
    responsible_role: str
    risk_class: str
    execution_class: str
    requires_model: bool
    preferred_worker_class: str
    requires_review: bool
    requires_human: bool
    requires_external_access: bool
    external_side_effect_class: str
    maximum_iterations: int
    maximum_model_calls: int
    maximum_external_calls: int
    money_limit_eur: float
    idempotency_key: str
    dependencies: list[str]
    blocking_gate: str
    success_condition: str
    failure_condition: str
    stop_condition: str
    evidence_references: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_plan_id(
    content_id: str,
    action_type: str,
    source_state_hash: str,
    queue_hash: str,
) -> str:
    """Compute a deterministic plan ID."""
    raw = f"{content_id}:{action_type}:{source_state_hash}:{queue_hash}"
    return f"PLAN-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def classify_action_risk(action_type: str, blocking_gate: str = "NONE") -> RiskClass:
    """Classify the risk level of an action."""
    if action_type in HIGH_RISK_ACTIONS or blocking_gate in {
        "AUDIENCE_DECISION_GATE",
        "PUBLICATION_APPROVAL_GATE",
        "SECURITY_GATE",
        "MONEY_GATE",
    }:
        return RiskClass.HIGH
    elif action_type in MEDIUM_RISK_ACTIONS or blocking_gate in {"PACKAGING_REQUIRED"}:
        return RiskClass.MEDIUM
    elif action_type in LOW_RISK_ACTIONS or blocking_gate in {"QC_REQUIRED", "NONE"}:
        return RiskClass.LOW
    else:
        return RiskClass.UNKNOWN


def determine_execution_class(
    action_type: str,
    status: str,
    requires_human: bool,
    requires_model: bool,
    maximum_external_calls: int,
) -> ExecutionClass:
    """Determine the execution class for a task."""
    if status == QueueItemStatus.UNKNOWN.value or action_type == "UNKNOWN_ACTION":
        return ExecutionClass.UNKNOWN
    if requires_human or status == QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value:
        return ExecutionClass.HUMAN_GATE
    if status == QueueItemStatus.COMPLETE_NO_ACTION.value or action_type == "IDLE_NO_ACTION":
        return ExecutionClass.NO_ACTION
    if maximum_external_calls > 0:
        return ExecutionClass.EXTERNAL_WRITE if "UPLOAD" in action_type or "MUTATION" in action_type else ExecutionClass.EXTERNAL_READ
    if requires_model:
        return ExecutionClass.MODEL_BUILD
    return ExecutionClass.DETERMINISTIC_LOCAL


class CreatorWorkPlanner:
    """Deterministic Autonomous Work Planner for Creator Factory."""

    def __init__(self, completed_task_ledger: dict[str, str] | None = None, active_tasks: set[str] | None = None):
        # Maps task_id -> state_hash_when_completed
        self.completed_task_ledger: dict[str, str] = completed_task_ledger or {}
        # Set of task_ids currently RUNNING
        self.active_tasks: set[str] = active_tasks or set()

    def generate_plan_for_item(
        self,
        item: CreatorWorkQueueItem,
        asset: CreatorAssetRecord,
        queue_hash: str = "",
    ) -> WorkPlan:
        """Derive a single deterministic WorkPlan from a queue item and asset record."""
        # 1. Money Gate check
        ok_money, _ = validate_finite_exact_zero(item.money_limit_eur)
        if not ok_money:
            raise ValueError(f"Invalid money limit: {item.money_limit_eur}")

        source_state_hash = asset.asset_state_hash
        task_id = f"TASK-CREATOR-{item.content_id}-{source_state_hash[:8]}"

        # 2. Risk and Execution Classification
        risk_cls = classify_action_risk(item.action_type, asset.current_blocking_gate)

        # Decide model requirement: deterministic checks preferred over model calls
        if item.action_type in {"LOCAL_QC_EXECUTION", "ASSET_VALIDATION", "INVENTORY_REFRESH", "QUEUE_DEDUPLICATION"}:
            requires_model = False
            preferred_worker = "LOCAL_DETERMINISTIC_RUNNER"
            max_model_calls = 0
        elif item.action_type in {"PACKAGE_PREPARATION", "METADATA_LINTING", "PROPOSAL_PREPARATION"}:
            requires_model = True
            preferred_worker = "BUILDER_MODEL"
            max_model_calls = 1
        elif item.requires_human:
            requires_model = False
            preferred_worker = "HUMAN_OPERATOR"
            max_model_calls = 0
        else:
            requires_model = False
            preferred_worker = "NONE"
            max_model_calls = 0

        exec_cls = determine_execution_class(
            action_type=item.action_type,
            status=item.status,
            requires_human=item.requires_human,
            requires_model=requires_model,
            maximum_external_calls=item.maximum_external_calls,
        )

        # 3. Duplicate Work Prevention
        # Check if identical task was already completed with identical state hash
        if task_id in self.completed_task_ledger and self.completed_task_ledger[task_id] == source_state_hash:
            plan_status = PlanStatus.NO_USEFUL_NEW_WORK.value
            exec_cls = ExecutionClass.NO_ACTION
            stop_condition = "TASK_ALREADY_COMPLETED_WITH_IDENTICAL_STATE_HASH"
        elif task_id in self.active_tasks:
            plan_status = PlanStatus.DUPLICATE_ACTIVE_TASK.value
            exec_cls = ExecutionClass.NO_ACTION
            stop_condition = "TASK_CURRENTLY_RUNNING_DUPLICATE_PREVENTED"
        elif item.status == QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value:
            plan_status = PlanStatus.WAITING_HUMAN.value
            stop_condition = "BLOCKED_AT_HUMAN_GATE_NO_AUTONOMOUS_OVERRIDE"
        elif item.status == QueueItemStatus.WAITING_FOR_TECHNICAL_REVIEW.value:
            plan_status = PlanStatus.WAITING_REVIEW.value
            stop_condition = "BLOCKED_AT_REVIEW_GATE"
        elif item.status == QueueItemStatus.COMPLETE_NO_ACTION.value:
            plan_status = PlanStatus.NO_USEFUL_NEW_WORK.value
            stop_condition = "ASSET_COMPLETE_NO_FURTHER_ACTION_NEEDED"
        elif risk_cls == RiskClass.UNKNOWN or exec_cls == ExecutionClass.UNKNOWN:
            plan_status = PlanStatus.BLOCKED_BY_POLICY.value
            stop_condition = "UNKNOWN_RISK_OR_EXECUTION_CLASS_FAIL_CLOSED"
        elif item.status == QueueItemStatus.READY_FOR_AUTONOMOUS_LOCAL_WORK.value:
            plan_status = PlanStatus.READY_TO_EXECUTE.value
            stop_condition = "EXECUTE_SINGLE_BOUNDED_ITERATION"
        else:
            plan_status = PlanStatus.UNKNOWN.value
            stop_condition = "UNRECOGNIZED_STATUS_FAIL_CLOSED"

        plan_id = compute_plan_id(item.content_id, item.action_type, source_state_hash, queue_hash)

        # Roles
        if exec_cls == ExecutionClass.HUMAN_GATE:
            responsible_role = "HUMAN_AUDIENCE_DECIDER" if "AUDIENCE" in item.action_type else "HUMAN_OPERATOR"
        elif item.action_type == "LOCAL_QC_EXECUTION":
            responsible_role = "LOCAL_QC_RUNNER"
        elif item.action_type == "PACKAGE_PREPARATION":
            responsible_role = "LOCAL_PACKAGER"
        else:
            responsible_role = "DISPATCHER"

        # Dependencies
        dependencies: list[str] = []
        if asset.media_master_path:
            dependencies.append(asset.media_master_path)
        if asset.qc_report_path:
            dependencies.append(asset.qc_report_path)

        return WorkPlan(
            plan_id=plan_id,
            plan_schema_version=PLAN_SCHEMA_VERSION,
            source_state_hash=source_state_hash,
            created_from_queue_hash=queue_hash,
            content_id=item.content_id,
            task_id=task_id,
            action_type=item.action_type,
            status=plan_status,
            responsible_role=responsible_role,
            risk_class=risk_cls.value,
            execution_class=exec_cls.value,
            requires_model=requires_model,
            preferred_worker_class=preferred_worker,
            requires_review=item.requires_independent_review or (risk_cls in {RiskClass.MEDIUM, RiskClass.HIGH}),
            requires_human=item.requires_human,
            requires_external_access=False,
            external_side_effect_class="NONE",
            maximum_iterations=1,  # Default exactly 1
            maximum_model_calls=max_model_calls,
            maximum_external_calls=0,  # Strict zero external calls
            money_limit_eur=0.0,
            idempotency_key=item.idempotency_key,
            dependencies=sorted(list(set(dependencies))),
            blocking_gate=asset.current_blocking_gate,
            success_condition=f"ACTION_{item.action_type}_COMPLETED_DETERMINISTICALLY",
            failure_condition="EXECUTION_ERROR_OR_SAFETY_GATE_VIOLATION",
            stop_condition=stop_condition,
            evidence_references=sorted(list(item.evidence_references)),
        )

    def plan_all(
        self,
        inventory: CreatorAssetInventory,
        queue: CreatorWorkQueue,
    ) -> list[WorkPlan]:
        """Generate deterministic WorkPlans for all items in the queue."""
        plans: list[WorkPlan] = []
        for item in queue.items:
            asset = inventory.assets.get(item.content_id)
            if asset is None:
                continue
            plan = self.generate_plan_for_item(item, asset, queue_hash=queue.queue_id)
            plans.append(plan)
        return plans

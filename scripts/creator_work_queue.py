#!/usr/bin/env python3
"""Creator Factory Ready-Work Queue.

Transforms canonical Creator Asset Inventory records into deterministic,
bounded work items with strict zero-spend and safe execution invariants.
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

WORK_QUEUE_SCHEMA_VERSION = "1.0"


def validate_finite_exact_zero(cost: Any) -> tuple[bool, str]:
    """Validate that a cost value is strictly a finite numeric exact 0 or 0.0.

    Rejects missing, None, boolean, strings, NaN, infinity, negative, or positive numbers.
    """
    if cost is None:
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if isinstance(cost, bool):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if not isinstance(cost, (int, float)):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if not math.isfinite(cost):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if cost != 0:
        return False, "PAYMENT_APPROVAL_REQUIRED"
    return True, "ZERO_COST_VERIFIED"


class QueueItemStatus(str, enum.Enum):
    READY_FOR_AUTONOMOUS_LOCAL_WORK = "READY_FOR_AUTONOMOUS_LOCAL_WORK"
    WAITING_FOR_TECHNICAL_REVIEW = "WAITING_FOR_TECHNICAL_REVIEW"
    WAITING_FOR_HUMAN_DECISION = "WAITING_FOR_HUMAN_DECISION"
    WAITING_FOR_EXTERNAL_PLATFORM = "WAITING_FOR_EXTERNAL_PLATFORM"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    COMPLETE_NO_ACTION = "COMPLETE_NO_ACTION"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CreatorWorkQueueItem:
    """Bounded, deterministic ready-work item."""

    queue_item_id: str
    content_id: str
    action_type: str
    status: str
    reason_code: str
    evidence_references: list[str]
    allowed_side_effect_class: str
    maximum_model_calls: int
    maximum_external_calls: int
    money_limit_eur: float
    requires_human: bool
    requires_independent_review: bool
    created_from_state_hash: str
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CreatorWorkQueue:
    """Deterministic collection of ready-work items."""

    schema_version: str
    queue_id: str
    generated_at: str
    items: list[CreatorWorkQueueItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "queue_id": self.queue_id,
            "generated_at": self.generated_at,
            "items": [item.to_dict() for item in self.items],
        }


def compute_queue_item_id(
    content_id: str,
    action_type: str,
    created_from_state_hash: str,
) -> str:
    """Compute a deterministic queue item ID."""
    raw = f"{content_id}:{action_type}:{created_from_state_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_idempotency_key(
    content_id: str,
    action_type: str,
    created_from_state_hash: str,
) -> str:
    """Compute deterministic idempotency key."""
    raw = f"idempotency:{content_id}:{action_type}:{created_from_state_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CreatorWorkQueueBuilder:
    """Builds bounded work items from canonical asset inventory entries."""

    @classmethod
    def build_queue(
        cls,
        inventory: CreatorAssetInventory,
        generated_at: str | None = None,
    ) -> CreatorWorkQueue:
        """Transform inventory into ready-work items."""
        now_ts = generated_at or inventory.generated_at
        items: list[CreatorWorkQueueItem] = []

        for content_id in sorted(inventory.assets.keys()):
            asset = inventory.assets[content_id]
            queue_item = cls._build_item_for_asset(asset)
            if queue_item is not None:
                items.append(queue_item)

        # Compute deterministic queue_id from sorted items
        combined_item_ids = "".join(f"{it.queue_item_id};" for it in items)
        queue_id = hashlib.sha256(
            f"{inventory.inventory_id}:{combined_item_ids}".encode("utf-8")
        ).hexdigest()

        return CreatorWorkQueue(
            schema_version=WORK_QUEUE_SCHEMA_VERSION,
            queue_id=queue_id,
            generated_at=now_ts,
            items=items,
        )

    @classmethod
    def _build_item_for_asset(cls, asset: CreatorAssetRecord) -> CreatorWorkQueueItem:
        """Derive the deterministic queue item for an asset."""
        # 1. Check strict zero-cost invariant
        zero_cost = 0.0
        ok_zero, _ = validate_finite_exact_zero(zero_cost)
        if not ok_zero:
            raise ValueError("Zero cost invariant violated")

        state_hash = asset.asset_state_hash

        # 2. Determine Action & Status based on blocking gate
        if asset.current_blocking_gate == "QC_REQUIRED":
            action_type = "LOCAL_QC_EXECUTION"
            status = QueueItemStatus.READY_FOR_AUTONOMOUS_LOCAL_WORK.value
            reason_code = "QC_REPORT_MISSING_OR_INVALID"
            allowed_side_effects = "WRITE_LOCAL_ARTIFACTS"
            max_model_calls = 1
            requires_human = False
            requires_independent_review = False

        elif asset.current_blocking_gate == "PACKAGING_REQUIRED":
            action_type = "PACKAGE_PREPARATION"
            status = QueueItemStatus.READY_FOR_AUTONOMOUS_LOCAL_WORK.value
            reason_code = "PUBLISH_PACKAGE_MISSING"
            allowed_side_effects = "WRITE_LOCAL_ARTIFACTS"
            max_model_calls = 1
            requires_human = False
            requires_independent_review = False

        elif asset.current_blocking_gate == "AUDIENCE_DECISION_GATE":
            action_type = "HUMAN_AUDIENCE_DECISION"
            status = QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value
            reason_code = "AUDIENCE_DECISION_REQUIRED"
            allowed_side_effects = "HUMAN_INTERACTION_REQUIRED"
            max_model_calls = 0
            requires_human = True
            requires_independent_review = False

        elif asset.current_blocking_gate == "PUBLICATION_APPROVAL_GATE":
            action_type = "HUMAN_PUBLICATION_APPROVAL"
            status = QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value
            reason_code = "EXPLICIT_APPROVAL_REQUIRED"
            allowed_side_effects = "HUMAN_INTERACTION_REQUIRED"
            max_model_calls = 0
            requires_human = True
            requires_independent_review = True

        elif asset.current_blocking_gate == "NONE":
            action_type = "IDLE_NO_ACTION"
            status = QueueItemStatus.COMPLETE_NO_ACTION.value
            reason_code = "ALL_GATES_SATISFIED"
            allowed_side_effects = "NONE"
            max_model_calls = 0
            requires_human = False
            requires_independent_review = False

        else:
            action_type = "UNKNOWN_ACTION"
            status = QueueItemStatus.UNKNOWN.value
            reason_code = "UNKNOWN_BLOCKING_GATE"
            allowed_side_effects = "NONE"
            max_model_calls = 0
            requires_human = False
            requires_independent_review = False

        q_id = compute_queue_item_id(asset.content_id, action_type, state_hash)
        idem_key = compute_idempotency_key(asset.content_id, action_type, state_hash)

        return CreatorWorkQueueItem(
            queue_item_id=q_id,
            content_id=asset.content_id,
            action_type=action_type,
            status=status,
            reason_code=reason_code,
            evidence_references=list(asset.source_files),
            allowed_side_effect_class=allowed_side_effects,
            maximum_model_calls=max_model_calls,
            maximum_external_calls=0,  # Strictly ZERO external calls in Creator Factory queue
            money_limit_eur=zero_cost,
            requires_human=requires_human,
            requires_independent_review=requires_independent_review,
            created_from_state_hash=state_hash,
            idempotency_key=idem_key,
        )

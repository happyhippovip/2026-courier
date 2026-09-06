#!/usr/bin/env python3
"""Creator Factory Chief / Dispatcher Handoff Contract.

Defines deterministic handoff representations for the organizational workflow:
Chief -> Dispatcher -> Specialist -> Result -> Chief.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.autonomous_continuation_policy import (
    PERMITTED_AUTONOMOUS_ACTIONS,
    STRICTLY_PROHIBITED_ACTIONS,
    AutonomousContinuationPolicyEngine,
    PolicyDecision,
)
from scripts.creator_asset_inventory import (
    CreatorAssetInventory,
    CreatorAssetRecord,
)
from scripts.creator_work_queue import (
    CreatorWorkQueue,
    CreatorWorkQueueItem,
    QueueItemStatus,
)

HANDOFF_SCHEMA_VERSION = "1.0"

# Review Trigger Philosophy Constants
MODEL_REVIEW_TRIGGER = "INFORMATION_GAIN_NOT_TIME"
NO_CHANGE = "NO_REVIEW"
SAME_DIFF_HASH = "NO_REVIEW"
SAME_TEST_HASH_AND_CODE_HASH = "REUSE_PREVIOUS_RESULT"
LOW_RISK_MODEL_REVIEW = "OPTIONAL_BATCHED"
MEDIUM_RISK_MODEL_REVIEW = "BEFORE_MAIN_PUSH"
HIGH_RISK_MODEL_REVIEW = "BEFORE_ACTIVATION"


@dataclass(frozen=True)
class CreatorHandoffContract:
    """Deterministic handoff contract for a single creator asset."""

    schema_version: str
    task_id: str
    content_id: str
    state_hash: str
    current_readiness: str
    blocker: str
    recommended_next_role: str
    permitted_actions: list[str]
    prohibited_actions: list[str]
    zero_cost_invariant: bool
    evidence_references: list[str]
    model_judgment_required: bool
    human_gate_required: bool
    review_recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreatorHandoffBuilder:
    """Constructs deterministic handoff contracts from asset records and queue items."""

    @classmethod
    def build_handoff_for_asset(
        cls,
        asset: CreatorAssetRecord,
        queue_item: CreatorWorkQueueItem | None = None,
    ) -> CreatorHandoffContract:
        """Construct handoff contract for a single asset."""
        task_id = f"TASK-CREATOR-{asset.content_id}-{asset.asset_state_hash[:8]}"

        # Role & Gate Determination
        if asset.current_blocking_gate == "AUDIENCE_DECISION_GATE":
            recommended_role = "HUMAN_AUDIENCE_DECIDER"
            human_gate = True
            model_judgment = False
            review_rec = HIGH_RISK_MODEL_REVIEW  # Before activation / publication
            permitted = []

        elif asset.current_blocking_gate == "PUBLICATION_APPROVAL_GATE":
            recommended_role = "HUMAN_PUBLICATION_APPROVER"
            human_gate = True
            model_judgment = False
            review_rec = HIGH_RISK_MODEL_REVIEW
            permitted = []

        elif asset.current_blocking_gate == "QC_REQUIRED":
            recommended_role = "LOCAL_QC_SPECIALIST"
            human_gate = False
            model_judgment = True
            review_rec = LOW_RISK_MODEL_REVIEW
            permitted = ["LOCAL_QC_EXECUTION", "ASSET_VALIDATION"]

        elif asset.current_blocking_gate == "PACKAGING_REQUIRED":
            recommended_role = "LOCAL_PACKAGING_SPECIALIST"
            human_gate = False
            model_judgment = True
            review_rec = MEDIUM_RISK_MODEL_REVIEW
            permitted = ["PACKAGE_PREPARATION", "METADATA_LINTING", "ASSET_VALIDATION"]

        elif asset.current_blocking_gate == "NONE":
            recommended_role = "DISPATCHER"
            human_gate = False
            model_judgment = False
            review_rec = NO_CHANGE
            permitted = ["INVENTORY_REFRESH", "QUEUE_DEDUPLICATION"]

        else:
            recommended_role = "CHIEF"
            human_gate = True
            model_judgment = True
            review_rec = MEDIUM_RISK_MODEL_REVIEW
            permitted = []

        return CreatorHandoffContract(
            schema_version=HANDOFF_SCHEMA_VERSION,
            task_id=task_id,
            content_id=asset.content_id,
            state_hash=asset.asset_state_hash,
            current_readiness=asset.current_technical_readiness_state,
            blocker=asset.current_blocking_gate,
            recommended_next_role=recommended_role,
            permitted_actions=sorted(list(set(permitted))),
            prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
            zero_cost_invariant=True,
            evidence_references=sorted(list(asset.source_files)),
            model_judgment_required=model_judgment,
            human_gate_required=human_gate,
            review_recommendation=review_rec,
        )

    @classmethod
    def build_handoff_manifest(
        cls,
        inventory: CreatorAssetInventory,
        queue: CreatorWorkQueue,
    ) -> dict[str, Any]:
        """Build full organization-level handoff manifest."""
        contracts: dict[str, Any] = {}
        queue_lookup = {item.content_id: item for item in queue.items}

        for cid in sorted(inventory.assets.keys()):
            asset = inventory.assets[cid]
            q_item = queue_lookup.get(cid)
            contract = cls.build_handoff_for_asset(asset, q_item)
            contracts[cid] = contract.to_dict()

        summary_hash = hashlib.sha256(
            json.dumps(contracts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "manifest_hash": summary_hash,
            "inventory_id": inventory.inventory_id,
            "queue_id": queue.queue_id,
            "generated_at": inventory.generated_at,
            "zero_cost_verified": True,
            "contracts": contracts,
        }

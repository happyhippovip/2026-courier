#!/usr/bin/env python3
"""Creator Factory Queue Runner & Production Handoff Generator.

Executes canonical inventory discovery, ready-work queue generation,
policy evaluation, and handoff manifest generation on real local assets.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.autonomous_continuation_policy import (
    AutonomousContinuationPolicyEngine,
)
from scripts.creator_asset_inventory import (
    CreatorAssetInventoryBuilder,
)
from scripts.creator_handoff_contract import (
    CreatorHandoffBuilder,
)
from scripts.creator_work_queue import (
    CreatorWorkQueueBuilder,
)


def run_creator_factory_pipeline(repo_dir: Path | None = None) -> dict:
    """Run full deterministic discovery, queue, policy, and handoff pipeline."""
    base_dir = repo_dir or REPO_ROOT
    builder = CreatorAssetInventoryBuilder(repo_dir=base_dir)

    # 1. Scan content directory
    inventory = builder.scan_content_directory()

    # 2. Build ready-work queue
    queue = CreatorWorkQueueBuilder.build_queue(inventory)

    # 3. Policy evaluation
    policy_results = {}
    for item in queue.items:
        res = AutonomousContinuationPolicyEngine.evaluate_queue_item(item)
        policy_results[item.content_id] = res.to_dict()

    # 4. Handoff manifest
    handoff_manifest = CreatorHandoffBuilder.build_handoff_manifest(inventory, queue)

    output_payload = {
        "inventory": inventory.to_dict(),
        "queue": queue.to_dict(),
        "policy_evaluations": policy_results,
        "handoff_manifest": handoff_manifest,
    }

    # 5. Save to events/ready-work/
    output_dir = base_dir / "events" / "ready-work"
    output_dir.mkdir(parents=True, exist_ok=True)
    status_file = output_dir / "creator_factory_status.json"
    status_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    return output_payload


if __name__ == "__main__":
    result = run_creator_factory_pipeline()
    print("=== CREATOR FACTORY STATUS GENERATED ===")
    print(f"Inventory Assets: {len(result['inventory']['assets'])}")
    print(f"Queue Items:     {len(result['queue']['items'])}")
    for item in result["queue"]["items"]:
        cid = item["content_id"]
        status = item["status"]
        pol = result["policy_evaluations"][cid]["decision"]
        print(f" - [{cid}]: queue_status={status}, policy_decision={pol}")

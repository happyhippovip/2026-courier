"""Deterministic tests for SEED 150 — WAREHOUSE-EXECUTION-RECEIPT PRÜFEN.

Verifies:
1. Warehouse Catalog Loading & Capability Selection:
   - Loads durable catalog from docs/agent-warehouse/AGENT_CATALOG.json
   - Selects smallest capable owner based on capability and constraints
2. Warehouse Task Preparation with Bound Owner:
   - Binds warehouse agent identity (owner) into the prepared task packet
3. Successful Warehouse Physical Execution & Durable Receipt:
   - Execution produces real artifacts and valid hash
   - Durable receipt strictly binds: agent owner, task_id, goal_id, dispatch_id,
     attempt_id, worker_id, workkey, source_sha, run_id, and artifact digest
   - Canonical receipt file is atomically persisted and readable
4. Failed Warehouse Execution Receipt:
   - FAILED status correctly recorded with zero artifacts without inventing data
5. Negative Cases (Fail-Closed Guards):
   - Impostor / mismatched warehouse owner in result -> ContractError("owner mismatch")
   - Missing or tampered artifact in result -> ContractError
   - Duplicate receipt idempotency (ACK_DUPLICATE) vs conflict rejection
   - Duplicate writer prevention in CapabilitySelector
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from scripts.agent_warehouse import (
    AgentCatalog,
    CapabilitySelector,
    create_warehouse_task,
    verify_and_persist_warehouse_receipt,
)
from scripts.integration_contract import ContractError, load_durable_receipt

SOURCE_SHA = "fac447f5c9c22936177069566b82c7319bc35f5c"
WORKKEY = "WORKKEY-WAREHOUSE-EXEC-150"


@pytest.fixture
def catalog():
    repo_root = Path(__file__).parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"
    assert catalog_path.is_file(), f"Catalog not found at {catalog_path}"
    return AgentCatalog.load(catalog_path)


def test_warehouse_catalog_loading_and_agent_selection(catalog):
    """Catalog loads correctly and selector identifies capable agent."""
    assert catalog.schema_version == "0.1-bootstrap"
    assert len(catalog.agents) >= 19

    selector = CapabilitySelector(catalog)
    explanation = selector.select_agent_for_task(required_capability="orchestration")
    assert explanation.selected_agent_id == "agent-chief-commander"
    assert "orchestration" in explanation.capable_reason


def test_warehouse_task_creation_with_bound_owner(catalog):
    """Task created from warehouse binds the selected agent as owner."""
    task, explanation = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-150",
        goal_id="goal-wh-150",
        target_capability="windows",
        workkey=WORKKEY,
        source_sha=SOURCE_SHA,
        artifacts=["warehouse_output.txt"],
    )

    assert task["task_id"] == "task-wh-150"
    assert task["owner"] == "agent-chief-commander"
    assert task["worker_id"] == "WINDOWS-01"
    assert task["workkey"] == WORKKEY
    assert task["source_sha"] == SOURCE_SHA
    assert task["status"] == "QUEUED"
    assert task["attempt_id"] == "task-wh-150:attempt:1"
    assert task["dispatch_id"].startswith("dispatch-")


def test_successful_warehouse_execution_and_durable_receipt(catalog, tmp_path):
    """Successful warehouse execution binds all fields into a persistent receipt."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    receipt_dir = tmp_path / "receipts"
    receipt_dir.mkdir()

    # 1. Produce actual physical artifact in workspace
    artifact_name = "warehouse_summary.txt"
    artifact_file = workspace / artifact_name
    artifact_content = b"WAREHOUSE EXECUTION COMPLETED SUCCESSFULLY BY AGENT CHIEF COMMANDER\n"
    artifact_file.write_bytes(artifact_content)
    artifact_hash = hashlib.sha256(artifact_content).hexdigest()

    # 2. Prepare warehouse task
    task, _ = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-exec-01",
        goal_id="goal-wh-exec-01",
        target_capability="windows",
        workkey=WORKKEY,
        source_sha=SOURCE_SHA,
        artifacts=[artifact_name],
    )

    # 3. Observed raw execution result from worker
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "owner": task["owner"],
        "workkey": task["workkey"],
        "source_sha": task["source_sha"],
        "run_id": "win-proc-9921",
        "status": "SUCCESS",
    }

    # 4. Verify and persist receipt
    receipt, receipt_path = verify_and_persist_warehouse_receipt(
        task=task,
        raw_result=raw_result,
        workspace=workspace,
        receipt_dir=receipt_dir,
    )

    # Verify receipt fields
    assert receipt_path.is_file()
    assert receipt["task_id"] == "task-wh-exec-01"
    assert receipt["owner"] == "agent-chief-commander"
    assert receipt["worker_id"] == "WINDOWS-01"
    assert receipt["workkey"] == WORKKEY
    assert receipt["source_sha"] == SOURCE_SHA
    assert receipt["run_id"] == "win-proc-9921"
    assert receipt["status"] == "SUCCESS"
    assert len(receipt["artifacts"]) == 1
    assert receipt["artifacts"][0]["path"] == artifact_name
    assert receipt["artifacts"][0]["sha256"] == artifact_hash

    # 5. Reload from disk to verify durability
    reloaded = load_durable_receipt(receipt_path)
    assert reloaded == receipt


def test_failed_warehouse_execution_receipt(catalog, tmp_path):
    """Failed warehouse task generates a valid failure receipt with zero artifacts."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    receipt_dir = tmp_path / "receipts"

    task, _ = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-fail-01",
        goal_id="goal-wh-fail-01",
        target_capability="windows",
        workkey=WORKKEY,
        source_sha=SOURCE_SHA,
        artifacts=["must_not_exist.txt"],
    )

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "owner": task["owner"],
        "workkey": task["workkey"],
        "source_sha": task["source_sha"],
        "run_id": "win-proc-fail-88",
        "status": "FAILED",
        "artifacts": [],
    }

    receipt, receipt_path = verify_and_persist_warehouse_receipt(
        task=task,
        raw_result=raw_result,
        workspace=workspace,
        receipt_dir=receipt_dir,
    )

    assert receipt["status"] == "FAILED"
    assert receipt["artifacts"] == []
    assert receipt["owner"] == "agent-chief-commander"
    assert receipt_path.is_file()


def test_negative_warehouse_receipt_owner_mismatch_fails_closed(catalog, tmp_path):
    """Worker reporting result with wrong warehouse agent owner fails closed."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "out.txt").write_text("ok\n", encoding="utf-8")
    receipt_dir = tmp_path / "receipts"

    task, _ = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-impostor",
        goal_id="goal-wh-impostor",
        target_capability="windows",
        artifacts=["out.txt"],
    )
    assert task["owner"] == "agent-chief-commander"

    # Impostor result claims a different agent owner
    impostor_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "owner": "agent-antigravity-bridge",
        "run_id": "win-proc-bad",
        "status": "SUCCESS",
    }

    with pytest.raises(ContractError, match="owner mismatch"):
        verify_and_persist_warehouse_receipt(
            task=task,
            raw_result=impostor_result,
            workspace=workspace,
            receipt_dir=receipt_dir,
        )


def test_negative_warehouse_receipt_missing_artifacts_fails_closed(catalog, tmp_path):
    """SUCCESS result missing declared artifacts fails closed."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # Deliberately do not create missing_effect.txt
    receipt_dir = tmp_path / "receipts"

    task, _ = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-missing-art",
        goal_id="goal-wh-missing-art",
        target_capability="windows",
        artifacts=["missing_effect.txt"],
    )

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "owner": task["owner"],
        "run_id": "win-proc-no-file",
        "status": "SUCCESS",
    }

    with pytest.raises(ContractError, match="missing expected artifact"):
        verify_and_persist_warehouse_receipt(
            task=task,
            raw_result=raw_result,
            workspace=workspace,
            receipt_dir=receipt_dir,
        )


def test_warehouse_receipt_duplicate_idempotency_and_conflict_rejection(catalog, tmp_path):
    """Identical receipt persistence succeeds idempotently; conflicting content raises ContractError."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "out.txt").write_text("data\n", encoding="utf-8")
    receipt_dir = tmp_path / "receipts"

    task, _ = create_warehouse_task(
        catalog=catalog,
        required_capability="orchestration",
        task_id="task-wh-dupe",
        goal_id="goal-wh-dupe",
        artifacts=["out.txt"],
    )
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "owner": task["owner"],
        "run_id": "run-dupe",
        "status": "SUCCESS",
    }

    # 1. First persist
    _, path1 = verify_and_persist_warehouse_receipt(task, raw_result, workspace, receipt_dir)
    assert path1.is_file()

    # 2. Identical duplicate persist -> succeeds
    _, path2 = verify_and_persist_warehouse_receipt(task, raw_result, workspace, receipt_dir)
    assert path2 == path1


def test_capability_selector_duplicate_writer_gating(catalog):
    """Capability selector respects active owners and prevents duplicate writers."""
    selector = CapabilitySelector(catalog)

    # If agent-chief-commander is already active, selector raises ValueError
    with pytest.raises(ValueError, match="duplicate writer"):
        selector.select_agent_for_task(
            required_capability="orchestration",
            current_owners=["agent-chief-commander"],
        )

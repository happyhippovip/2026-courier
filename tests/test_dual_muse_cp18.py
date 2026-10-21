"""Contract tests for CP-18 / P18: Dual Muse Execution under Shared Capacity Limit.

Acceptance Criteria:
1. Genau zwei unterschiedliche harmlose Lesetasks vorbereitet (two-task-inputs, zero cost).
2. Zwei Task-/Attempt-/Result-Ketten mit zeitlicher Überlappung belegbar.
3. Fensteranzahl allein zählt NICHT als Beweis.
4. Gemeinsame Kapazitätsgrenze: MAX_CONCURRENCY = 2; KEIN dritter Worker (fail-closed).
5. Physische Ausführung nur über vorhandenen erlaubten Adapter und gesondertes Live-Budget.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Cross-platform stub for Unix fcntl if on Windows
if "fcntl" not in sys.modules:
    try:
        import fcntl
    except ImportError:
        sys.modules["fcntl"] = MagicMock()

import pytest

# Add mac_worker directory to sys.path so muse_adapter can import runtime_state
_mac_worker_dir = str(Path(__file__).resolve().parent.parent / "scripts" / "mac_worker")
if _mac_worker_dir not in sys.path:
    sys.path.insert(0, _mac_worker_dir)

import muse_adapter

from courier_core.dual_muse_capacity_gate import (
    DualMuseCapacityGate,
    CapacityLimitExceededError,
    LiveBudgetGateError,
    READ_TASK_ALPHA,
    READ_TASK_BETA,
    ExecutionChain,
    DualExecutionEvidence,
)


def test_two_harmless_read_task_inputs_specification():
    """CP-18 Acceptance: Genau zwei unterschiedliche harmlose Lesetasks (zero mutation, zero spend)."""
    assert READ_TASK_ALPHA.task_id != READ_TASK_BETA.task_id
    assert READ_TASK_ALPHA.target_file != READ_TASK_BETA.target_file
    assert READ_TASK_ALPHA.effect_class == "read_only"
    assert READ_TASK_BETA.effect_class == "read_only"
    assert READ_TASK_ALPHA.estimated_cost_eur == 0.0
    assert READ_TASK_BETA.estimated_cost_eur == 0.0

    task_a = READ_TASK_ALPHA.to_task_dict()
    task_b = READ_TASK_BETA.to_task_dict()

    assert task_a["status"] == "QUEUED"
    assert task_b["status"] == "QUEUED"
    assert task_a["artifacts"] == ["readme_headings.json"]
    assert task_b["artifacts"] == ["test_config_summary.json"]


def test_dual_execution_under_shared_capacity_limit_succeeds():
    """CP-18 Acceptance: Zwei Task-/Attempt-/Result-Ketten mit zeitlicher Überlappung belegbar."""
    gate = DualMuseCapacityGate(max_concurrency=2)

    # 1. Start Task Alpha in Slot 1
    att_1, dsp_1 = gate.acquire_slot("slot_1", READ_TASK_ALPHA.to_task_dict(), attempt=1)
    assert att_1 == "muse-read-alpha-001:attempt:1"
    assert dsp_1 == "dsp-slot_1-muse-read-alpha-001"

    # Brief delay to establish distinct start timestamps
    time.sleep(0.05)

    # 2. Start Task Beta in Slot 2 while Slot 1 is still active (Temporal Overlap)
    att_2, dsp_2 = gate.acquire_slot("slot_2", READ_TASK_BETA.to_task_dict(), attempt=1)
    assert att_2 == "muse-read-beta-002:attempt:1"
    assert dsp_2 == "dsp-slot_2-muse-read-beta-002"

    time.sleep(0.05)

    # 3. Release Slot 1 with cryptographic result digest
    chain_1 = gate.release_slot("slot_1", result_digest="sha256-digest-alpha-headings-001")
    assert chain_1.status == "SUCCESS"
    assert chain_1.result_digest == "sha256-digest-alpha-headings-001"

    # 4. Release Slot 2 with cryptographic result digest
    chain_2 = gate.release_slot("slot_2", result_digest="sha256-digest-beta-config-002")
    assert chain_2.status == "SUCCESS"
    assert chain_2.result_digest == "sha256-digest-beta-config-002"

    # 5. Verify Temporal Overlap & Generate Dual Execution Evidence
    evidence = DualMuseCapacityGate.generate_dual_execution_evidence(chain_1, chain_2)
    assert evidence.has_temporal_overlap is True
    assert evidence.overlap_duration_s > 0.0
    assert evidence.third_worker_prevented is True
    assert evidence.window_count_alone_rejected is True


def test_third_concurrent_worker_is_strictly_blocked():
    """CP-18 Acceptance: Gemeinsame Kapazitätsgrenze: KEIN dritter Worker."""
    gate = DualMuseCapacityGate(max_concurrency=2)

    # Acquire Slot 1 and Slot 2
    gate.acquire_slot("slot_1", READ_TASK_ALPHA.to_task_dict())
    gate.acquire_slot("slot_2", READ_TASK_BETA.to_task_dict())

    # Attempt to acquire a 3rd concurrent worker: MUST FAIL CLOSED
    with pytest.raises(CapacityLimitExceededError) as exc_info:
        gate.acquire_slot("slot_1", {"task_id": "third-task-attempt"})
    assert "A 3rd concurrent worker is strictly prohibited" in str(exc_info.value)

    # Attempt to acquire an invalid slot: MUST FAIL CLOSED
    with pytest.raises(CapacityLimitExceededError) as exc_info_slot:
        gate.acquire_slot("slot_3", {"task_id": "third-slot-task"})
    assert "A 3rd concurrent worker is strictly prohibited" in str(exc_info_slot.value)


def test_window_count_alone_is_not_proof():
    """CP-18 Acceptance: Fensteranzahl allein zählt nicht als Beweis."""
    # Dummy window count (e.g. 5 open tabs) without verified chains and overlap fails
    chain_isolated_1 = ExecutionChain(
        slot_id="slot_1",
        goal_id="g1",
        task_id="t1",
        attempt_id="t1:attempt:1",
        dispatch_id="d1",
        result_id="r1",
        start_time=100.0,
        end_time=110.0,
        result_digest="digest-1",
    )
    # Sequential (non-overlapping) chain
    chain_isolated_2 = ExecutionChain(
        slot_id="slot_2",
        goal_id="g1",
        task_id="t2",
        attempt_id="t2:attempt:1",
        dispatch_id="d2",
        result_id="r2",
        start_time=120.0,
        end_time=130.0,
        result_digest="digest-2",
    )

    has_overlap, duration = DualMuseCapacityGate.verify_temporal_overlap(chain_isolated_1, chain_isolated_2)
    assert has_overlap is False
    assert duration == 0.0

    with pytest.raises(ValueError) as exc:
        DualMuseCapacityGate.generate_dual_execution_evidence(chain_isolated_1, chain_isolated_2)
    assert "Executions did not overlap in time" in str(exc.value)


def test_live_budget_gate_enforces_zero_spend_limit():
    """CP-18 Acceptance: Physische Ausführung erfordert gesondertes freigegebenes Live-Budget."""
    gate_unfunded = DualMuseCapacityGate(live_budget_approved=False)

    # Dry-run / zero spend check passes
    gate_unfunded.check_live_budget(requires_physical_spend=False)

    # Physical execution with spend attempt fails closed
    with pytest.raises(LiveBudgetGateError) as exc:
        gate_unfunded.check_live_budget(requires_physical_spend=True)
    assert "AUTONOMOUS_SPEND_LIMIT_EUR = 0.00" in str(exc.value)

    # Funded gate allows execution
    gate_funded = DualMuseCapacityGate(live_budget_approved=True)
    gate_funded.check_live_budget(requires_physical_spend=True)


def test_muse_adapter_integration_contract(tmp_path):
    """CP-18 Acceptance: Integration mit Muse-Adapter und Slot-Isolierung."""
    ws_slot1 = str((tmp_path / "slot_1_workspace").resolve())
    ws_slot2 = str((tmp_path / "slot_2_workspace").resolve())
    Path(ws_slot1).mkdir(parents=True)
    Path(ws_slot2).mkdir(parents=True)

    task_1 = {
        "goal_id": "g-muse-dual",
        "task_id": "muse-read-alpha-001",
        "attempt_id": "muse-read-alpha-001:attempt:1",
        "dispatch_id": "dsp-slot_1",
        "instruction": "Read headers",
    }
    task_2 = {
        "goal_id": "g-muse-dual",
        "task_id": "muse-read-beta-002",
        "attempt_id": "muse-read-beta-002:attempt:1",
        "dispatch_id": "dsp-slot_2",
        "instruction": "Read pytest config",
    }

    # Verify task_binding guarantees distinct slots and workspaces
    binding_1 = muse_adapter.task_binding(task_1, "slot_1", ws_slot1)
    binding_2 = muse_adapter.task_binding(task_2, "slot_2", ws_slot2)

    assert binding_1["slot_id"] == "slot_1"
    assert binding_2["slot_id"] == "slot_2"
    assert binding_1["workspace"] != binding_2["workspace"]

    # Verify build_muse_command enforces headless-v1 protocol
    caps = {"protocol": "headless-v1", "binary": "muse"}
    cmd_1, _ = muse_adapter.build_muse_command(
        task_1, None, caps, slot_id="slot_1", workspace=ws_slot1, prompt="Run harmless read 1"
    )
    cmd_2, _ = muse_adapter.build_muse_command(
        task_2, None, caps, slot_id="slot_2", workspace=ws_slot2, prompt="Run harmless read 2"
    )

    assert "muse" in cmd_1[0]
    assert cmd_1[1] == "exec"
    assert cmd_1[3] == binding_1["workspace"]
    assert "muse" in cmd_2[0]
    assert cmd_2[3] == binding_2["workspace"]

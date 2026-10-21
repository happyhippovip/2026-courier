"""Tests for CP-20 / CQ-20 / GB-HANDOFF-01: Task Handoff, Attempt Lineage & Effect State

Verifies:
1. Fehlversuch bleibt Historie: Prior attempts are retained immutably in lineage.
2. Kein Cross-Project-Kontextleck: Substitute workers without project authorization fail closed.
3. Inkompatibler Ersatz wird abgewiesen: Missing capabilities, wrong effect class, or invalid platform rejected.
4. Unbekannter Effekt wird vor Retry geklärt: UNKNOWN_EFFECT quarantines task and blocks retries until reconciliation.
5. Required evidence generated: ['task-contract', 'attempt-lineage', 'effect-state'].
"""

import pytest

from courier_core.task_handoff import (
    AttemptRecord,
    AttemptStatus,
    CrossProjectContextLeakError,
    EffectReconciliationDecision,
    EffectState,
    IncompatibleSubstituteWorkerError,
    TaskHandoffCoordinator,
    UnresolvedEffectError,
    WorkerProfile,
)


def test_failed_attempt_remains_immutable_history():
    coord = TaskHandoffCoordinator()
    task = coord.register_task(
        task_id="task-101",
        project_id="proj-core",
        goal_id="goal-42",
        required_capabilities={"python", "git"},
        effect_class="idempotent",
    )

    worker_a = WorkerProfile(
        worker_id="worker-alpha",
        authorized_projects={"proj-core"},
        supported_capabilities={"python", "git", "powershell"},
        supported_effect_classes={"idempotent", "read_only"},
        platform="windows",
    )

    worker_b = WorkerProfile(
        worker_id="worker-beta",
        authorized_projects={"proj-core"},
        supported_capabilities={"python", "git", "bash"},
        supported_effect_classes={"idempotent", "read_only"},
        platform="windows",
    )

    # 1. First Attempt on Worker A
    att1 = coord.handoff_to_substitute_worker("task-101", worker_a, now=100.0)
    assert att1.attempt_number == 1
    assert att1.worker_id == "worker-alpha"
    assert att1.status == AttemptStatus.RUNNING

    # Worker A fails
    coord.record_attempt_terminal(
        task_id="task-101",
        attempt_number=1,
        status=AttemptStatus.FAILED,
        effect_state=EffectState.NO_EFFECT,
        failure_reason="Process out of memory",
        finished_at=115.0,
    )

    # 2. Handoff to Worker B creates Attempt 2
    att2 = coord.handoff_to_substitute_worker("task-101", worker_b, now=120.0)
    assert att2.attempt_number == 2
    assert att2.worker_id == "worker-beta"
    assert att2.status == AttemptStatus.RUNNING

    # 3. Assert complete history preservation
    lineage = task.attempt_lineage
    assert len(lineage) == 2

    # Attempt 1 is immutable and preserved
    assert lineage[0].attempt_number == 1
    assert lineage[0].worker_id == "worker-alpha"
    assert lineage[0].status == AttemptStatus.FAILED
    assert lineage[0].failure_reason == "Process out of memory"
    assert lineage[0].started_at == 100.0
    assert lineage[0].finished_at == 115.0

    # Attempt 2 is recorded with next sequence
    assert lineage[1].attempt_number == 2
    assert lineage[1].worker_id == "worker-beta"
    assert lineage[1].status == AttemptStatus.RUNNING
    assert lineage[1].started_at == 120.0


def test_cross_project_context_leak_is_blocked():
    coord = TaskHandoffCoordinator()
    coord.register_task(
        task_id="task-secret-audit",
        project_id="proj-finance",
        goal_id="goal-audit",
        required_capabilities={"python"},
        effect_class="read_only",
    )

    unauthorized_worker = WorkerProfile(
        worker_id="worker-marketing",
        authorized_projects={"proj-marketing", "proj-analytics"},
        supported_capabilities={"python"},
        supported_effect_classes={"read_only"},
        platform="windows",
    )

    # Attempting handoff across projects raises CrossProjectContextLeakError
    with pytest.raises(CrossProjectContextLeakError, match="Cross-project boundary violation"):
        coord.handoff_to_substitute_worker("task-secret-audit", unauthorized_worker)

    # Lineage remains clean (zero attempts created)
    task = coord.get_task("task-secret-audit")
    assert len(task.attempt_lineage) == 0


def test_incompatible_substitute_worker_is_rejected():
    coord = TaskHandoffCoordinator()
    coord.register_task(
        task_id="task-heavy-build",
        project_id="proj-ci",
        goal_id="goal-ci",
        required_capabilities={"python", "docker"},
        effect_class="non_idempotent",
        allowed_platforms={"windows"},
    )

    # Case A: Missing required capability 'docker'
    worker_no_docker = WorkerProfile(
        worker_id="worker-light",
        authorized_projects={"proj-ci"},
        supported_capabilities={"python"},
        supported_effect_classes={"non_idempotent"},
        platform="windows",
    )
    with pytest.raises(IncompatibleSubstituteWorkerError, match="lacks required capabilities: \\['docker'\\]"):
        coord.handoff_to_substitute_worker("task-heavy-build", worker_no_docker)

    # Case B: Unsupported effect class
    worker_read_only = WorkerProfile(
        worker_id="worker-ro",
        authorized_projects={"proj-ci"},
        supported_capabilities={"python", "docker"},
        supported_effect_classes={"read_only"},
        platform="windows",
    )
    with pytest.raises(IncompatibleSubstituteWorkerError, match="does not support effect class 'non_idempotent'"):
        coord.handoff_to_substitute_worker("task-heavy-build", worker_read_only)

    # Case C: Platform mismatch (task requires 'windows', worker is 'linux')
    worker_linux = WorkerProfile(
        worker_id="worker-linux",
        authorized_projects={"proj-ci"},
        supported_capabilities={"python", "docker"},
        supported_effect_classes={"non_idempotent"},
        platform="linux",
    )
    with pytest.raises(IncompatibleSubstituteWorkerError, match="not in allowed platforms \\['windows'\\]"):
        coord.handoff_to_substitute_worker("task-heavy-build", worker_linux)


def test_unknown_effect_quarantine_blocks_retry_until_reconciled():
    coord = TaskHandoffCoordinator()
    task = coord.register_task(
        task_id="task-bank-transfer",
        project_id="proj-core",
        goal_id="goal-tx",
        required_capabilities={"python"},
        effect_class="non_idempotent",
    )

    worker = WorkerProfile(
        worker_id="worker-tx",
        authorized_projects={"proj-core"},
        supported_capabilities={"python"},
        supported_effect_classes={"non_idempotent"},
        platform="windows",
    )

    # Attempt 1 starts
    coord.handoff_to_substitute_worker("task-bank-transfer", worker, now=100.0)

    # Worker crashes with unverified network socket: UNKNOWN_EFFECT
    coord.record_attempt_terminal(
        task_id="task-bank-transfer",
        attempt_number=1,
        status=AttemptStatus.FAILED,
        effect_state=EffectState.UNKNOWN_EFFECT,
        failure_reason="Network dropped during gateway commit",
        finished_at=105.0,
    )

    assert task.quarantined is True
    assert task.current_effect_state == EffectState.UNKNOWN_EFFECT

    # Attempting handoff to replacement worker is strictly BLOCKED
    with pytest.raises(UnresolvedEffectError, match="unresolved UNKNOWN_EFFECT"):
        coord.handoff_to_substitute_worker("task-bank-transfer", worker, now=110.0)

    # Reconcile: Proven that transaction was NOT executed at gateway
    coord.reconcile_unresolved_effect(
        task_id="task-bank-transfer",
        decision=EffectReconciliationDecision.PROVEN_NOT_EXECUTED,
        evidence_digest="gateway-audit-tx-absent-digest",
        reconciled_by="audit-ledger-officer",
    )

    assert task.quarantined is False
    assert task.current_effect_state == EffectState.NO_EFFECT

    # Now handoff to attempt 2 succeeds safely
    att2 = coord.handoff_to_substitute_worker("task-bank-transfer", worker, now=120.0)
    assert att2.attempt_number == 2
    assert att2.status == AttemptStatus.RUNNING


def test_reconciliation_confirmed_executed_completes_task_without_redundant_attempt():
    coord = TaskHandoffCoordinator()
    task = coord.register_task(
        task_id="task-deploy",
        project_id="proj-ops",
        goal_id="goal-deploy",
        required_capabilities={"python"},
        effect_class="non_idempotent",
    )

    worker = WorkerProfile(
        worker_id="worker-ops",
        authorized_projects={"proj-ops"},
        supported_capabilities={"python"},
        supported_effect_classes={"non_idempotent"},
        platform="windows",
    )

    coord.handoff_to_substitute_worker("task-deploy", worker, now=200.0)

    coord.record_attempt_terminal(
        task_id="task-deploy",
        attempt_number=1,
        status=AttemptStatus.FAILED,
        effect_state=EffectState.UNKNOWN_EFFECT,
        failure_reason="Worker lost connection before reporting ack",
        finished_at=210.0,
    )

    # Reconcile: Proven that deploy WAS confirmed executed
    coord.reconcile_unresolved_effect(
        task_id="task-deploy",
        decision=EffectReconciliationDecision.CONFIRMED_EXECUTED,
        evidence_digest="cluster-pod-live-sha",
        reconciled_by="deploy-verifier",
    )

    assert task.is_completed is True
    assert task.current_effect_state == EffectState.EFFECT_COMMITTED

    # Any further handoff is rejected because task is already complete
    with pytest.raises(RuntimeError, match="already completed"):
        coord.handoff_to_substitute_worker("task-deploy", worker, now=220.0)


def test_generate_handoff_evidence():
    coord = TaskHandoffCoordinator()
    coord.register_task(
        task_id="task-evidence-test",
        project_id="proj-demo",
        goal_id="goal-demo",
        required_capabilities={"python", "git"},
        effect_class="idempotent",
    )

    worker = WorkerProfile(
        worker_id="worker-demo",
        authorized_projects={"proj-demo"},
        supported_capabilities={"python", "git"},
        supported_effect_classes={"idempotent"},
        platform="windows",
    )

    coord.handoff_to_substitute_worker("task-evidence-test", worker, now=1.0)
    coord.record_attempt_terminal(
        task_id="task-evidence-test",
        attempt_number=1,
        status=AttemptStatus.COMPLETED,
        effect_state=EffectState.EFFECT_COMMITTED,
        finished_at=5.0,
    )

    evidence = coord.generate_handoff_evidence("task-evidence-test")

    assert evidence["required_evidence"] == ["task-contract", "attempt-lineage", "effect-state"]
    assert evidence["task-contract"]["task_id"] == "task-evidence-test"
    assert evidence["task-contract"]["project_id"] == "proj-demo"
    assert len(evidence["attempt-lineage"]) == 1
    assert evidence["attempt-lineage"][0]["status"] == "COMPLETED"
    assert evidence["effect-state"]["current_effect_state"] == "EFFECT_COMMITTED"
    assert evidence["effect-state"]["is_completed"] is True

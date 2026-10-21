"""Comprehensive Contract Tests for CP-12 / CQ-12:
Recovery: Unterscheidung von langsamer Arbeit, toten Workern und erforderlichen Dauerprozessen.

Acceptance Criteria:
1. Langsame, gesunde Arbeit wird geschützt (PRESERVE_AND_WAIT).
2. Tote Worker werden identifiziert, scoped geerntet und geordnet reconciliert/quarantäniert.
3. Erforderliche Dauerprozesse (Services/Daemons) bleiben erhalten (Service- vs. Job-Status-Trennung).
4. Keine pauschalen Kills (Reaping beschränkt sich auf den Job-Prozessbaum).
5. Kein DONE aus Timeout (Invariante: Timeouts können keinen Erfolg erfinden).
"""

from __future__ import annotations

import time
import pytest

from courier_core.workload_classifier import (
    WorkloadClassifier,
    WorkloadKind,
    WorkloadLivenessState,
    RecommendedAction,
    TaskExecutionPolicy,
    IllegalDoneFromTimeoutError,
)


def test_healthy_slow_work_is_preserved_and_not_killed():
    """Beweist: Langsame Arbeit mit kontinuierlichem Fortschritt oder aktiven Heartbeats

    wird als HEALTHY_SLOW_WORK eingestuft und NICHT abgebrochen oder gekillt.
    """
    classifier = WorkloadClassifier(alive_checker=lambda pid: True)

    t0 = 1000.0
    now = t0 + 200.0  # Läuft bereits 200s (lange Ausführung)
    last_progress = now - 15.0  # Fortschritt vor 15s (innerhalb 60s Grace)
    last_hb = now - 5.0  # Heartbeat vor 5s (frisch)

    policy = TaskExecutionPolicy(timeout_s=300.0, progress_grace_s=60.0, heartbeat_ttl_s=30.0)

    report = classifier.classify_and_resolve(
        workload_id="task-heavy-render",
        pid=1234,
        started_at=t0,
        last_progress_at=last_progress,
        last_heartbeat_at=last_hb,
        policy=policy,
        current_time=now,
        execute_reap=True,
    )

    # KERNERGEBNIS:
    assert report.state == WorkloadLivenessState.HEALTHY_SLOW_WORK
    assert report.action == RecommendedAction.PRESERVE_AND_WAIT
    assert report.job_status == "RUNNING"
    assert report.service_status == "SERVICE_HEALTHY"
    assert report.reaped_tree is False


def test_dead_worker_reaped_and_quarantined_without_blind_retry():
    """Beweist: Ein toter Worker wird erkannt. Bei nicht-idempotenter Arbeit

    erfolgt Quarantäne (HUMAN_REQUIRED), kein blindes Replay.
    """
    reaped_pids = []
    classifier = WorkloadClassifier(
        alive_checker=lambda pid: False,  # Prozess ist tot
        tree_killer=lambda pid, timeout: reaped_pids.append(pid),
    )

    t0 = 2000.0
    now = t0 + 100.0
    policy = TaskExecutionPolicy(effect_class="non_idempotent", heartbeat_ttl_s=30.0)

    report = classifier.classify_and_resolve(
        workload_id="task-db-write",
        pid=5555,
        started_at=t0,
        last_progress_at=t0,
        last_heartbeat_at=t0,  # Heartbeat veraltet (100s her)
        policy=policy,
        current_time=now,
        execute_reap=True,
    )

    # KERNERGEBNISSE:
    assert report.state == WorkloadLivenessState.DEAD_WORKER
    assert report.action == RecommendedAction.REAP_JOB_TREE_AND_QUARANTINE
    assert report.job_status == "HUMAN_REQUIRED"
    assert report.service_status == "SERVICE_HEALTHY"
    assert 5555 in reaped_pids
    assert report.reaped_tree is True


def test_dead_worker_idempotent_task_cleared_safely_for_retry():
    """Beweist: Bei toten Workern mit idempotenter Aufgabe ist ein sicherer Retry zulässig."""
    reaped_pids = []
    classifier = WorkloadClassifier(
        alive_checker=lambda pid: False,
        tree_killer=lambda pid, timeout: reaped_pids.append(pid),
    )

    t0 = 3000.0
    now = t0 + 80.0
    policy = TaskExecutionPolicy(effect_class="idempotent", heartbeat_ttl_s=30.0)

    report = classifier.classify_and_resolve(
        workload_id="task-safe-read",
        pid=6666,
        started_at=t0,
        last_progress_at=t0,
        last_heartbeat_at=t0,
        policy=policy,
        current_time=now,
        execute_reap=True,
    )

    assert report.state == WorkloadLivenessState.DEAD_WORKER
    assert report.action == RecommendedAction.REAP_JOB_TREE_AND_RETRY
    assert report.job_status == "QUEUED"
    assert 6666 in reaped_pids


def test_persistent_service_preserved_and_never_broad_killed():
    """Beweist: Erforderliche Dauerprozesse (Courier Hub, Daemons)

    werden als PERSISTENT_SERVICE geschützt; pauschale Kills sind verboten.
    """
    reaped_pids = []
    classifier = WorkloadClassifier(
        alive_checker=lambda pid: True,
        tree_killer=lambda pid, timeout: reaped_pids.append(pid),
    )

    t0 = 4000.0
    now = t0 + 86400.0  # Läuft seit 24 Stunden (Dienst)
    policy = TaskExecutionPolicy(is_service=True)

    report = classifier.classify_and_resolve(
        workload_id="service-courier-hub",
        pid=1001,
        started_at=t0,
        last_progress_at=now - 10.0,
        last_heartbeat_at=now - 2.0,
        policy=policy,
        current_time=now,
        execute_reap=True,
    )

    assert report.kind == WorkloadKind.PERSISTENT_SERVICE
    assert report.state == WorkloadLivenessState.SERVICE_HEALTHY
    assert report.action == RecommendedAction.PRESERVE_SERVICE
    assert report.service_status == "SERVICE_HEALTHY"
    # Invariante: Kein Prozesskill gegen gesunde Dauerprozesse!
    assert reaped_pids == []
    assert report.reaped_tree is False


def test_stuck_job_reaps_only_job_tree_while_service_remains_healthy():
    """Beweist: Trennung von Service-Status und Job-Status.

    Wenn ein Job die Deadline überschreitet und hängt, wird nur der Job-Prozessbaum
    beendet. Der übergeordnete Dienst bleibt SERVICE_HEALTHY erhalten.
    """
    reaped_pids = []
    classifier = WorkloadClassifier(
        alive_checker=lambda pid: True,  # Prozess existiert noch, hängt aber
        tree_killer=lambda pid, timeout: reaped_pids.append(pid),
    )

    t0 = 5000.0
    now = t0 + 500.0  # Timeout (Policy limit 300s überschritten)
    last_progress = t0 + 10.0  # Fortschritt steht seit 490s still
    last_hb = now - 5.0  # Worker-Daemon sendet Heartbeats weiter
    policy = TaskExecutionPolicy(timeout_s=300.0, progress_grace_s=60.0, effect_class="non_idempotent")

    report = classifier.classify_and_resolve(
        workload_id="task-stuck-freeze",
        pid=7777,
        started_at=t0,
        last_progress_at=last_progress,
        last_heartbeat_at=last_hb,
        policy=policy,
        current_time=now,
        execute_reap=True,
    )

    # KERNERGEBNISSE:
    assert report.state == WorkloadLivenessState.STUCK_JOB_EXPIRED
    assert report.action == RecommendedAction.REAP_JOB_TREE_AND_QUARANTINE
    assert report.job_status == "HUMAN_REQUIRED"
    assert report.service_status == "SERVICE_HEALTHY"  # Dienst bleibt intakt!
    assert 7777 in reaped_pids
    assert report.reaped_tree is True


def test_invariant_enforce_no_done_from_timeout():
    """Beweist: Kein DONE aus Timeout.

    Ein Timeout oder Hänger darf niemals als DONE oder SUCCESS deklariert werden.
    """
    classifier = WorkloadClassifier()

    # Versuche illegale Status-Transformation
    with pytest.raises(IllegalDoneFromTimeoutError, match="Cannot mark task as DONE due to"):
        classifier.enforce_no_done_from_timeout("DONE", "task_execution_timeout_exceeded")

    with pytest.raises(IllegalDoneFromTimeoutError, match="Cannot mark task as SUCCESS due to"):
        classifier.enforce_no_done_from_timeout("SUCCESS", "timeout_grace_expired")

    with pytest.raises(IllegalDoneFromTimeoutError, match="Cannot mark task as COMPLETED due to"):
        classifier.enforce_no_done_from_timeout("COMPLETED", "worker_heartbeat_timeout")

    # Gültige Status-Transformationen auf Fehler / Quarantäne sind erlaubt:
    classifier.enforce_no_done_from_timeout("HUMAN_REQUIRED", "task_execution_timeout_exceeded")
    classifier.enforce_no_done_from_timeout("FAILED_TERMINAL", "task_execution_timeout_exceeded")
    classifier.enforce_no_done_from_timeout("QUEUED", "task_execution_timeout_exceeded")

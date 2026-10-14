"""Targeted tests for L5 Desktop Hub Founder Project Base (lane L5).

Tests pure projection logic and real in-process HubServer endpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import tempfile
import threading
import requests
import pytest

from courier_core.state_machine import TaskStatus
from courier_hub import project_base
from courier_hub.server import Hub, HubServer


# ------------------------------------------------------------------ helpers
@dataclass
class DummyTask:
    task_id: str
    status: Any
    adapter: str = "synthetic"
    params: Any = None
    effect_class: str = "non_idempotent"
    max_attempts: int = 3
    lease_ttl_s: int = 6
    timeout_s: Optional[int] = None
    attempt: int = 1
    dispatch_id: Optional[str] = None
    worker_id: Optional[str] = None
    started: int = 0
    pending_result_id: Optional[str] = None
    accepted_result_id: Optional[str] = None
    cancel_requested: int = 0
    failure_kind: Optional[str] = None
    retryable: int = 1
    last_reason: Optional[str] = None
    late_results: int = 0
    resolution: Optional[str] = None
    decided_by: Optional[str] = None
    created_seq: int = 1
    updated_seq: int = 2


@dataclass
class DummyEvent:
    seq: int
    event_id: str
    type: str
    task_id: Optional[str] = None
    attempt: Optional[int] = None
    dispatch_id: Optional[str] = None
    worker_id: Optional[str] = None
    result_id: Optional[str] = None
    dedupe_key: Optional[str] = None
    ts_utc: str = "2026-10-08T00:00:00Z"
    payload: Any = None
    prev_hash: str = "0000"
    hash: str = "abcd"
    schema_v: int = 1


# ------------------------------------------------------------------ unit tests
def test_extract_workkeys_filters_terminal_and_extracts_metadata():
    tasks = [
        DummyTask(task_id="t1", status=TaskStatus.RUNNING, worker_id="mac-worker",
                  params={"workkey": "L5-PROJECT-BASE"}, adapter="mac_worker", attempt=1),
        DummyTask(task_id="t2", status=TaskStatus.BLOCKED, worker_id="mac-worker",
                  params={"workkey": "L4-VERIFIER"}, adapter="local_json", attempt=2),
        DummyTask(task_id="t3", status=TaskStatus.COMPLETE, worker_id="mac-worker",
                  resolution="verified", params={"workkey": "L2-JOURNAL"}, attempt=1),
    ]
    events_by_task = {
        "t1": [DummyEvent(seq=1, event_id="e1", type="TASK_STARTED", task_id="t1", ts_utc="2026-10-08T01:00:00Z")],
        "t2": [DummyEvent(seq=2, event_id="e2", type="TASK_BLOCKED", task_id="t2", ts_utc="2026-10-08T01:05:00Z")],
    }

    wks = project_base.extract_workkeys(tasks, events_by_task)
    # Only t1 and t2 should be present (t3 is complete)
    assert len(wks) == 2
    # Blocked task t2 is sorted first
    assert wks[0]["task_id"] == "t2"
    assert wks[0]["workkey"] == "L4-VERIFIER"
    assert wks[0]["status"] == "BLOCKED"
    assert wks[0]["attempt"] == 2

    assert wks[1]["task_id"] == "t1"
    assert wks[1]["workkey"] == "L5-PROJECT-BASE"
    assert wks[1]["worker_id"] == "mac-worker"
    assert wks[1]["started_at"] == "2026-10-08T01:00:00Z"


def test_extract_last_verified_result_identifies_latest_accepted_evidence():
    tasks = [
        DummyTask(task_id="t1", status=TaskStatus.COMPLETE, resolution="verified",
                  accepted_result_id="res-1", updated_seq=10),
        DummyTask(task_id="t2", status=TaskStatus.COMPLETE, resolution="verified",
                  accepted_result_id="res-2", updated_seq=25),
        DummyTask(task_id="t3", status=TaskStatus.COMPLETE, resolution="human_confirmed",
                  accepted_result_id="res-3", updated_seq=30),
    ]
    events_by_task = {
        "t1": [
            DummyEvent(seq=10, event_id="e1", type="RESULT_ACCEPTED", task_id="t1", hash="hash1"),
        ],
        "t2": [
            DummyEvent(seq=20, event_id="e2", type="RESULT_READY", task_id="t2",
                       payload={"artifacts": [{"path": "/out/proof.json", "sha256": "abc123"}]}),
            DummyEvent(seq=25, event_id="e3", type="RESULT_ACCEPTED", task_id="t2", hash="hash2"),
        ],
    }

    res = project_base.extract_last_verified_result(tasks, events_by_task)
    assert res is not None
    assert res["task_id"] == "t2"
    assert res["result_id"] == "res-2"
    assert res["seq"] == 25
    assert res["hash"] == "hash2"
    assert len(res["evidence"]) == 1
    assert res["evidence"][0]["name"] == "proof.json"
    assert res["evidence"][0]["hash"] == "abc123"


def test_extract_last_verified_result_none_when_no_verified_tasks():
    tasks = [
        DummyTask(task_id="t1", status=TaskStatus.RUNNING),
        DummyTask(task_id="t2", status=TaskStatus.FAILED),
    ]
    res = project_base.extract_last_verified_result(tasks, {})
    assert res is None


def test_calculate_away_summary_aggregates_events_since_seq():
    events = [
        DummyEvent(seq=5, event_id="e5", type="TASK_STARTED", task_id="t1"),
        DummyEvent(seq=10, event_id="e10", type="TASK_COMPLETE", task_id="t1"),
        DummyEvent(seq=15, event_id="e15", type="TASK_STARTED", task_id="t2"),
        DummyEvent(seq=20, event_id="e20", type="TASK_BLOCKED", task_id="t2",
                   payload={"reason": "Ambiguous outcome"}),
        DummyEvent(seq=25, event_id="e25", type="TASK_FAILED", task_id="t3",
                   payload={"reason": "Crash"}),
    ]

    away = project_base.calculate_away_summary(events, since_seq=10)
    assert away["since_seq"] == 10
    assert away["events_count"] == 3
    assert away["completed_count"] == 0  # seq 10 was not strictly > 10
    assert away["started_count"] == 1
    assert away["blocked_count"] == 1
    assert away["failed_count"] == 1
    assert len(away["milestones"]) == 3
    assert away["milestones"][1]["kind"] == "BLOCKED"


def test_calculate_next_safe_action_priorities():
    # 1. Needs you decision
    piles_needs = {
        "needs_you": [{"id": "t1", "title": "Confirm payment", "next": "Ask person"}],
        "working": [{"id": "t2", "title": "Worker task"}],
        "done": [],
    }
    action1 = project_base.calculate_next_safe_action(piles_needs, controller_status="running")
    assert action1["type"] == "DECISION_REQUIRED"
    assert action1["urgency"] == "HIGH"
    assert action1["task_id"] == "t1"

    # 2. Controller inactive
    piles_idle = {"needs_you": [], "working": [], "done": []}
    action2 = project_base.calculate_next_safe_action(piles_idle, controller_status="unreachable")
    assert action2["type"] == "CONTROLLER_INACTIVE"
    assert action2["urgency"] == "HIGH"

    # 3. Active execution
    piles_working = {"needs_you": [], "working": [{"id": "t2", "title": "Worker task"}], "done": []}
    action3 = project_base.calculate_next_safe_action(piles_working, controller_status="running")
    assert action3["type"] == "MONITOR_EXECUTION"
    assert action3["urgency"] == "NORMAL"

    # 4. System idle
    action4 = project_base.calculate_next_safe_action(piles_idle, controller_status="running")
    assert action4["type"] == "IDLE_READY"
    assert action4["urgency"] == "LOW"


def test_build_project_base_structure():
    tasks = [
        DummyTask(task_id="t1", status=TaskStatus.COMPLETE, resolution="verified", updated_seq=5),
    ]
    events = [
        DummyEvent(seq=1, event_id="e1", type="TASK_CREATED", task_id="t1"),
        DummyEvent(seq=5, event_id="e5", type="TASK_COMPLETE", task_id="t1"),
    ]
    events_by_task = {"t1": events}

    pb = project_base.build_project_base(
        tasks, events_by_task, all_events=events, head=(5, "hash5"),
        controller_status="running", since_seq=0
    )

    assert "piles" in pb
    assert "counts" in pb
    assert "current_workkeys" in pb
    assert "last_verified_result" in pb
    assert "away_summary" in pb
    assert "next_safe_action" in pb
    assert "durable_context" in pb
    assert pb["durable_context"]["repository"] == "happyhippovip/2026-courier"
    assert pb["durable_context"]["trunk_branch"] == "integration/v1"
    assert pb["durable_context"]["head_seq"] == 5


# ------------------------------------------------------------------ HTTP integration test
def test_hub_project_base_http_endpoint():
    with tempfile.TemporaryDirectory() as td:
        from courier_core.journal import Journal
        from courier_core.events import Event, EventType
        db_path = Path(td) / "courier.db"
        j = Journal(db_path).open()
        e1 = Event(
            type=EventType.TASK_CREATED,
            task_id="task-live-1",
            payload={"adapter": "synthetic", "params": {"workkey": "LIVE-PB-1"}, "effect_class": "non_idempotent", "max_attempts": 3, "lease_ttl_s": 30},
            event_id="ev-1",
            ts_utc="2026-10-08T00:00:00Z",
        )
        j.append(e1)
        e_claim = Event(
            type=EventType.TASK_CLAIMED,
            task_id="task-live-1",
            attempt=1,
            dispatch_id="disp-1",
            worker_id="mac-worker",
            payload={"ttl_s": 30},
            event_id="ev-claim",
            ts_utc="2026-10-08T00:00:30Z",
        )
        j.append(e_claim)
        e2 = Event(
            type=EventType.TASK_STARTED,
            task_id="task-live-1",
            attempt=1,
            dispatch_id="disp-1",
            worker_id="mac-worker",
            payload={},
            event_id="ev-2",
            ts_utc="2026-10-08T00:01:00Z",
        )
        j.append(e2)
        j.close()

        hub = Hub(Path(td), "http://127.0.0.1:9999", actor="desktop:founder")
        server = HubServer(hub, 0)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            url = f"{server.url}hub/api/project_base"
            resp = requests.get(url, timeout=5)
            assert resp.status_code == 200
            data = resp.json()

            assert "counts" in data
            assert data["counts"]["active_workkeys"] == 1
            assert len(data["current_workkeys"]) == 1
            assert data["current_workkeys"][0]["workkey"] == "LIVE-PB-1"
            # With controller unreachable, founder is alerted that controller is inactive
            assert data["next_safe_action"]["type"] == "CONTROLLER_INACTIVE"
            assert data["durable_context"]["total_tasks"] == 1
            assert data["durable_context"]["head_seq"] == 3

            # With controller running, active workkeys yield MONITOR_EXECUTION
            hub.status = lambda: {"controller": "running"}
            resp_running = requests.get(url, timeout=5)
            data_running = resp_running.json()
            assert data_running["next_safe_action"]["type"] == "MONITOR_EXECUTION"

            # Test since_seq query param
            resp_since = requests.get(f"{url}?since_seq=1", timeout=5)
            assert resp_since.status_code == 200
            data_since = resp_since.json()
            assert data_since["away_summary"]["since_seq"] == 1
            assert data_since["away_summary"]["events_count"] == 2  # ev-claim (2) and ev-2 (3)
        finally:
            server.shutdown()
            server.server_close()

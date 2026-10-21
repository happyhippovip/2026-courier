"""CP-07 / CQ-07 / P07 Transaction Boundary & ACK Contract for Durable Queue.

Acceptance:
- Bestaetigte Aufgaben ueberleben Neustart (Persistence boundary).
- Nicht bestaetigte Eingaben bleiben als Draft erhalten (Draft preservation).
- Keine zweite autoritative Queue (Single authoritative queue invariant).
Required Evidence:
- ['queue-storage', 'transaction-boundary', 'ACK-contract']
"""

import hashlib
import json
import pytest
from pathlib import Path

from server import app as server_app
from courier_core.ack_boundary import (
    AckBoundaryError,
    AckReceipt,
    ClientDraftStore,
    DurableQueueTransactionBoundary,
    UncommittedCrashError,
)


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    draft_file = tmp_path / "drafts.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    http = server_app.app.test_client()
    draft_store = ClientDraftStore(draft_file)
    return http, draft_store, state_file, draft_file


def auth():
    return {"Authorization": "Bearer test-secret"}


def _plan(instruction: str = "bounded step"):
    return [
        {
            "task_id": "task-cp07-1",
            "target_agent": "linux",
            "instruction": instruction,
            "artifacts": ["artifact.txt"],
        }
    ]


def test_confirmed_goal_survives_cold_restart(test_env):
    http, draft_store, state_file, _ = test_env

    # 1. User inputs a new goal into the UI (saved to draft store)
    draft_id = "draft-101"
    goal_text = "Deploy and verify production pipeline"
    draft_store.save_draft(draft_id, goal_text, module="core")

    # 2. Commit and ACK through transaction boundary
    payload = {
        "goal_text": goal_text,
        "workflow_plan": _plan("run production gate"),
    }
    receipt = DurableQueueTransactionBoundary.commit_and_ack(
        http,
        draft_store,
        draft_id,
        payload,
        headers=auth(),
    )

    # 3. ACK verified and draft cleared from client cache
    assert isinstance(receipt, AckReceipt)
    assert receipt.committed is True
    assert receipt.status == "ACTIVE"
    assert draft_store.get_draft(draft_id) is None

    # 4. Cold restart: Simulating complete server shutdown and reboot
    state_after_crash = json.loads(state_file.read_text(encoding="utf-8"))
    assert receipt.goal_id in state_after_crash["goals"]
    assert "task-cp07-1" in state_after_crash["tasks"]
    assert state_after_crash["tasks"]["task-cp07-1"]["status"] == "QUEUED"


def test_unconfirmed_input_persists_as_draft_when_crash_before_commit(test_env):
    http, draft_store, state_file, _ = test_env

    draft_id = "draft-unconfirmed-202"
    goal_text = "Unconfirmed draft that must survive crash"
    draft_store.save_draft(draft_id, goal_text, module="billing")

    payload = {
        "goal_text": goal_text,
        "workflow_plan": _plan(),
    }

    # Simulate client crash / network power loss BEFORE physical commit barrier
    with pytest.raises(UncommittedCrashError):
        DurableQueueTransactionBoundary.commit_and_ack(
            http,
            draft_store,
            draft_id,
            payload,
            headers=auth(),
            simulate_crash_before_fsync=True,
        )

    # Invariant: Draft MUST remain preserved in client draft store
    surviving_draft = draft_store.get_draft(draft_id)
    assert surviving_draft is not None
    assert surviving_draft.goal_text == goal_text

    # Invariant: Central state file has NO phantom goal or partial task
    state = server_app.load_state()
    assert len(state["goals"]) == 0
    assert len(state["tasks"]) == 0


def test_crash_after_commit_before_ack_is_reconciled_via_idempotent_retry(test_env):
    http, draft_store, state_file, _ = test_env

    draft_id = "draft-reconcile-303"
    goal_text = "Idempotent recovery after dropped ACK"
    draft_store.save_draft(draft_id, goal_text)

    payload = {
        "goal_text": goal_text,
        "workflow_plan": _plan(),
    }

    # First attempt: Server committed, but network died before client received ACK
    with pytest.raises(UncommittedCrashError):
        DurableQueueTransactionBoundary.commit_and_ack(
            http,
            draft_store,
            draft_id,
            payload,
            headers=auth(),
            simulate_crash_after_fsync_before_ack=True,
        )

    # Draft is still in draft store because client did not see the ACK
    assert draft_store.get_draft(draft_id) is not None

    # Client recovers and retries the exact same draft
    receipt = DurableQueueTransactionBoundary.commit_and_ack(
        http,
        draft_store,
        draft_id,
        payload,
        headers=auth(),
    )
    assert receipt.committed is True
    # Draft is now safely cleared
    assert draft_store.get_draft(draft_id) is None

    # Exactly one goal exists in state (no duplication)
    state = server_app.load_state()
    assert len(state["goals"]) == 1
    assert len(state["tasks"]) == 1


def test_no_second_queue_invariant(test_env):
    http, draft_store, _, _ = test_env

    # 1. Normal state with client drafts passes
    draft_store.save_draft("d1", "clean text")
    state = server_app.load_state()
    DurableQueueTransactionBoundary.verify_no_second_queue(state, draft_store)

    # 2. Rogue draft attempting to act as secondary queue by attaching task authority
    rogue_draft = draft_store.save_draft("d-rogue", "rogue task", task_id="task-rogue-1", status="QUEUED")
    with pytest.raises(AckBoundaryError, match="authoritative task fields"):
        DurableQueueTransactionBoundary.verify_no_second_queue(state, draft_store)


def test_draft_store_file_backed_persistence(tmp_path):
    store_file = tmp_path / "persistent_drafts.json"
    store1 = ClientDraftStore(store_file)
    store1.save_draft("d-persist", "Important notes for tomorrow", priority="high")

    # Simulate process termination and reload
    store2 = ClientDraftStore(store_file)
    loaded = store2.get_draft("d-persist")
    assert loaded is not None
    assert loaded.goal_text == "Important notes for tomorrow"
    assert loaded.metadata["priority"] == "high"

    # Clearing updates disk
    assert store2.clear_draft("d-persist") is True
    store3 = ClientDraftStore(store_file)
    assert store3.get_draft("d-persist") is None

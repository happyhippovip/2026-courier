"""Tests for CP-41 / CQ-41 / GB-COMPOSER-DRAFT-01: Composer Draft & Concurrent Typing Coordinator.

Verifies:
1. Concurrent user input typed while submit is in flight is preserved ("Neue Eingabe bleibt erhalten").
2. Server ACK surgically clears only the confirmed draft snapshot ("Bestätigung löscht genau alten Draft").
3. Double-clicks and retry replays produce zero duplicate goals ("Doppelklick und Retry erzeugen keine doppelten Goals").
4. Failed submissions preserve active draft buffer without data loss.
5. Evidence structure generation containing ['draft-state', 'client-request-id', 'ACK-handler'].
"""

import pytest

from courier_core.composer_draft_manager import (
    ComposerDraftManager,
    DraftSnapshot,
    SnapshotNotFoundError,
    SnapshotStatus,
)


def test_concurrent_typing_preserved_on_ack():
    """User submits initial text, continues typing concurrently, and ACK clears only the submitted portion."""
    manager = ComposerDraftManager(initial_text="Build feature Alpha")

    # User presses Submit -> snapshot captured
    snap = manager.create_submit_snapshot(client_request_id="req-alpha-001")
    assert snap.content == "Build feature Alpha"
    assert snap.status == SnapshotStatus.PENDING_SUBMIT

    # While submit is in-flight, user concurrently types more into the composer
    manager.append_current_text(" and also start Beta architecture")
    assert manager.current_text == "Build feature Alpha and also start Beta architecture"

    # Server responds with ACK
    handled = manager.handle_ack(client_request_id="req-alpha-001", goal_id="goal-alpha-101")
    assert handled is True

    # Critical invariant: New concurrent input MUST be preserved, old draft surgically removed!
    assert manager.current_text == "and also start Beta architecture"
    goals = manager.list_created_goals()
    assert len(goals) == 1
    assert goals[0]["goal_id"] == "goal-alpha-101"
    assert goals[0]["content"] == "Build feature Alpha"


def test_exact_draft_cleared_on_ack():
    """If no new text was typed during submit, buffer is cleanly cleared on ACK."""
    manager = ComposerDraftManager(initial_text="Deploy release v1.0")

    manager.create_submit_snapshot(client_request_id="req-dep-002")
    assert manager.current_text == "Deploy release v1.0"

    manager.handle_ack(client_request_id="req-dep-002", goal_id="goal-dep-202")
    assert manager.current_text == ""


def test_double_click_protection_zero_duplicate_goals():
    """Rapid double-click or network retry with same client_request_id creates zero duplicate goals."""
    manager = ComposerDraftManager(initial_text="Audit access logs")

    # Rapid click 1
    snap1 = manager.create_submit_snapshot(client_request_id="req-audit-double")
    # Rapid click 2 (double click)
    snap2 = manager.create_submit_snapshot(client_request_id="req-audit-double")

    assert snap1.snapshot_id == snap2.snapshot_id

    # ACK for click 1
    handled1 = manager.handle_ack(client_request_id="req-audit-double", goal_id="goal-audit-001")
    assert handled1 is True

    # Repeated duplicate ACK / retry response
    handled2 = manager.handle_ack(client_request_id="req-audit-double", goal_id="goal-audit-001")
    assert handled2 is False  # Idempotent no-op

    # Only 1 goal was registered
    goals = manager.list_created_goals()
    assert len(goals) == 1
    assert goals[0]["goal_id"] == "goal-audit-001"


def test_failed_submission_preserves_input():
    """Submission failure marks snapshot FAILED but retains composer text."""
    manager = ComposerDraftManager(initial_text="Export database dump")

    manager.create_submit_snapshot(client_request_id="req-fail-003")
    manager.handle_failure(client_request_id="req-fail-003", reason="Gateway timeout 504")

    # Text must remain in composer
    assert manager.current_text == "Export database dump"
    assert len(manager.list_created_goals()) == 0


def test_unknown_ack_raises_error():
    """ACK for nonexistent client_request_id raises SnapshotNotFoundError."""
    manager = ComposerDraftManager()

    with pytest.raises(SnapshotNotFoundError):
        manager.handle_ack(client_request_id="req-unknown-999", goal_id="goal-999")


def test_evidence_generation():
    """Validates required catalog evidence keys: ['draft-state', 'client-request-id', 'ACK-handler']."""
    manager = ComposerDraftManager(initial_text="Test Task")
    manager.create_submit_snapshot("req-ev-1")
    manager.handle_ack("req-ev-1", "goal-ev-1")

    evidence = manager.generate_composer_evidence()

    assert "draft-state" in evidence
    assert "client-request-id" in evidence
    assert "ACK-handler" in evidence

    assert evidence["draft-state"]["acknowledged_count"] == 1
    assert "req-ev-1" in evidence["client-request-id"]
    assert evidence["ACK-handler"]["created_goals_count"] == 1
    assert evidence["ACK-handler"]["goals"] == ["goal-ev-1"]

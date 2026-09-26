"""Focused contract tests for scripts.attestation_contract (P1 ledger identity).

Covers the derivations server/app.py depends on: principal binding,
result fingerprinting, and fail-closed receipt freshness.
"""

import copy

import pytest

from scripts.attestation_contract import (
    ContractError,
    current_receipt,
    fingerprint,
    principal,
)

pytestmark = pytest.mark.fast


def _live_state():
    binding = {"sha": "abc", "runtime": "courier-server:1"}
    task = {
        "goal_id": "g1",
        "task_id": "t1",
        "attempt_id": "t1:attempt:1",
        "dispatch_id": "d1",
        "execution_ref": "exec-1",
        "result": {"result_id": "res-1", "status": "SUCCESS", "artifacts": []},
    }
    receipt = {
        "attestation_id": "a1",
        "goal_id": "g1",
        "task_id": "t1",
        "attempt_id": "t1:attempt:1",
        "dispatch_id": "d1",
        "execution_ref": "exec-1",
        "result_id": "res-1",
        "result_sha256": fingerprint(task["result"]),
        "artifacts": [],
        "producer_principal": principal("prod-secret"),
        "verifier_principal": principal("ver-secret"),
        "binding": copy.deepcopy(binding),
        "verdict": "PASS",
    }
    goal = {"goal_id": "g1", "workflow_plan": [{"task_id": "t1"}]}
    return receipt, task, goal, binding


def test_principal_matches_request_derivation():
    from server.app import API_KEY, app, get_auth_principal

    with app.test_request_context(headers={"Authorization": f"Bearer {API_KEY}"}):
        assert get_auth_principal() == principal(API_KEY)


def test_principal_rejects_empty_secret():
    with pytest.raises(ContractError):
        principal("")
    with pytest.raises(ContractError):
        principal(None)


def test_fingerprint_deterministic_and_sensitive():
    result = {"b": [1, 2], "a": "x"}
    assert fingerprint(result) == fingerprint({"a": "x", "b": [1, 2]})
    assert fingerprint(result) != fingerprint({"a": "x", "b": [1, 3]})
    with pytest.raises(ContractError):
        fingerprint("not-a-dict")


def test_current_receipt_accepts_live_state():
    receipt, task, goal, binding = _live_state()
    assert current_receipt(receipt, task, goal, binding, receipt["producer_principal"],
                           receipt["verifier_principal"]) is True


def test_current_receipt_rejects_drift():
    receipt, task, goal, binding = _live_state()
    for mutate in (
        lambda r: r.update(binding={"sha": "other", "runtime": "x"}),
        lambda r: r.update(producer_principal="principal_other"),
        lambda r: r.update(verdict="FAIL"),
        lambda r: r.update(task_id="t-other"),
    ):
        tampered = copy.deepcopy(receipt)
        mutate(tampered)
        assert current_receipt(tampered, task, goal, binding,
                               receipt["producer_principal"],
                               receipt["verifier_principal"]) is False


def test_current_receipt_rejects_stale_result():
    receipt, task, goal, binding = _live_state()
    task["result"] = {"result_id": "res-2", "status": "SUCCESS", "artifacts": []}
    assert current_receipt(receipt, task, goal, binding,
                           receipt["producer_principal"],
                           receipt["verifier_principal"]) is False


def test_current_receipt_rejects_missing_goal():
    receipt, task, _, binding = _live_state()
    assert current_receipt(receipt, task, {}, binding,
                           receipt["producer_principal"],
                           receipt["verifier_principal"]) is False


def test_current_receipt_rejects_bad_types():
    receipt, task, goal, binding = _live_state()
    with pytest.raises(ContractError):
        current_receipt(None, task, goal, binding, "p", "v")

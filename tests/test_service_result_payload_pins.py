"""P9 result-payload pins for courier_worker.service (tests only).

Covers two pure, offline functions that have no dedicated service test
file at the base tree and that the open service-hardening PRs do not
target (those pin argv, startup/token/watcher lifecycle, cancel-watcher
parsing, client-init URL validation, artifact-prefix scoping and
outbox durability):

- build_result_payload: worker-outcome mapping (retryable vs terminal),
  bridged-run report rules (a missing report is a non-retryable failure,
  report failures propagate retryability, reasons truncate at 500 chars),
  the success golden shape (no retryable/reason keys), and artifact path
  scoping relative to home.
- resolve_spec: fail-closed claim validation (non-dict claims, missing
  ids, bool/non-int attempts, bad ttl_s, out-of-bounds timeout_s,
  heartbeat_s minimum mapping, the result_id length bound, and bridge
  refusals for argv-carrying or non-allowlisted specs).

No network, no subprocesses, no credentials; all paths stay under tmp_path.
"""

from __future__ import annotations

import os

import pytest

from courier_worker.host import (
    ArtifactRef,
    ExecutionResult,
    ExecutionSpec,
    Outcome,
    SpecError,
)
from courier_worker.service import build_result_payload, resolve_spec

EFFECT_KEY = "cfx-" + "a" * 40


def _spec(home: str, dispatch_id: str = "d1", adapter=None) -> ExecutionSpec:
    return ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id=dispatch_id,
        worker_id="w1",
        result_id="r-" + dispatch_id,
        argv=("python", "runner.py", "req.json"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
        heartbeat_s=2.0,
        adapter=adapter,
        params={} if adapter is not None else None,
        effect_key=EFFECT_KEY if adapter is not None else None,
    )


def _result(home: str, outcome: str, dispatch_id: str = "d1", adapter=None,
            artifacts=()) -> ExecutionResult:
    return ExecutionResult(
        spec=_spec(home, dispatch_id, adapter),
        outcome=outcome,
        returncode=0 if outcome == Outcome.COMPLETED else 1,
        artifacts=tuple(artifacts),
    )


def _claim(**overrides):
    claim = {
        "task_id": "t1",
        "dispatch_id": "d1",
        "attempt": 1,
        "ttl_s": 30,
        "spec": {
            "adapter": "synthetic",
            "params": {"write": "out.txt", "content": "hello"},
            "effect_key": EFFECT_KEY,
            "timeout_s": 30,
        },
    }
    claim.update(overrides)
    return claim


# -- build_result_payload: worker outcomes ------------------------------------

def test_timeout_outcome_is_retryable_failure(tmp_path):
    result = _result(str(tmp_path), Outcome.TIMEOUT)
    payload = build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert payload["reason"] == "worker outcome: timeout"


def test_lease_lost_outcome_is_retryable_failure(tmp_path):
    result = _result(str(tmp_path), Outcome.LEASE_LOST)
    payload = build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True


def test_cancelled_outcome_is_not_retryable(tmp_path):
    result = _result(str(tmp_path), Outcome.CANCELLED)
    payload = build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert "cancelled" in payload["reason"]


def test_crash_outcome_carries_worker_reason(tmp_path):
    result = _result(str(tmp_path), Outcome.CRASH)
    payload = build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["reason"] == "worker outcome: crash"


# -- build_result_payload: bridged success needs a report ---------------------

def test_bridged_success_without_report_is_nonretryable_failure(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(result, None, home=str(tmp_path))
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert "no structured result" in payload["reason"]


def test_bridged_success_with_success_report_is_success(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(
        result, {"outcome": "success", "reason": "", "retryable": False},
        home=str(tmp_path))
    assert payload["outcome"] == "success"
    assert "retryable" not in payload
    assert "reason" not in payload


def test_bridged_report_failure_propagates_retryable(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(
        result, {"outcome": "failure", "reason": "boom", "retryable": True},
        home=str(tmp_path))
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert payload["reason"] == "boom"


def test_bridged_report_reason_truncates_at_500_chars(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(
        result, {"outcome": "failure", "reason": "r" * 600, "retryable": False},
        home=str(tmp_path))
    assert payload["reason"] == "r" * 500


def test_bridged_report_failure_without_reason_gets_default(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(
        result, {"outcome": "failure", "retryable": False}, home=str(tmp_path))
    assert payload["reason"] == "adapter reported failure"


def test_bridged_report_failure_without_retryable_defaults_false(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED, adapter="synthetic")
    payload = build_result_payload(
        result, {"outcome": "failure", "reason": "x"}, home=str(tmp_path))
    assert payload["retryable"] is False


# -- build_result_payload: artifact scoping -----------------------------------

def test_artifacts_scoped_under_home(tmp_path):
    home = str(tmp_path)
    artifacts = (ArtifactRef(path="out.txt", sha256="abc"),)
    result = _result(home, Outcome.COMPLETED, adapter=None, artifacts=artifacts)
    payload = build_result_payload(result, home=home)
    assert payload["artifacts"] == [{"path": "artifacts/d1/out.txt", "sha256": "abc"}]


def test_artifacts_unscoped_without_home(tmp_path):
    artifacts = (ArtifactRef(path="out.txt", sha256="abc"),)
    result = _result(str(tmp_path), Outcome.COMPLETED, artifacts=artifacts)
    payload = build_result_payload(result)
    assert payload["artifacts"] == [{"path": "out.txt", "sha256": "abc"}]


def test_artifacts_outside_home_keep_raw_path(tmp_path):
    home = str(tmp_path / "home")
    outside = str(tmp_path / "elsewhere")
    spec = ExecutionSpec(
        task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1",
        result_id="r-d1", argv=("python", "x"), timeout_s=30.0,
        lease_ttl_s=30.0, artifact_dir=outside, heartbeat_s=2.0)
    result = ExecutionResult(
        spec=spec, outcome=Outcome.COMPLETED,
        artifacts=(ArtifactRef(path="out.txt", sha256="abc"),))
    payload = build_result_payload(result, home=home)
    assert payload["artifacts"] == [{"path": "out.txt", "sha256": "abc"}]


def test_success_payload_has_golden_shape(tmp_path):
    result = _result(str(tmp_path), Outcome.COMPLETED)
    payload = build_result_payload(result, home=str(tmp_path))
    assert payload["dispatch_id"] == "d1"
    assert payload["result_id"] == "r-d1"
    assert payload["outcome"] == "success"
    assert set(payload) == {"dispatch_id", "result_id", "artifacts", "outcome"}


# -- resolve_spec: fail-closed validation -------------------------------------

def test_resolve_spec_rejects_non_dict_claim(tmp_path):
    with pytest.raises(SpecError):
        resolve_spec(["not", "a", "dict"], "w1", str(tmp_path), 2.0)


@pytest.mark.parametrize("field", ["task_id", "dispatch_id"])
def test_resolve_spec_rejects_missing_ids(tmp_path, field):
    claim = _claim()
    del claim[field]
    with pytest.raises(SpecError):
        resolve_spec(claim, "w1", str(tmp_path), 2.0)


@pytest.mark.parametrize("attempt", [True, False, 0, -2, "1", 1.5, None])
def test_resolve_spec_rejects_bad_attempt(tmp_path, attempt):
    with pytest.raises(SpecError):
        resolve_spec(_claim(attempt=attempt), "w1", str(tmp_path), 2.0)


@pytest.mark.parametrize("ttl", [0, -3, "30", None, [30]])
def test_resolve_spec_rejects_bad_ttl(tmp_path, ttl):
    with pytest.raises(SpecError):
        resolve_spec(_claim(ttl_s=ttl), "w1", str(tmp_path), 2.0)


@pytest.mark.parametrize("timeout", [-5, "30", 99999, [30]])
def test_resolve_spec_rejects_bad_timeout(tmp_path, timeout):
    claim = _claim()
    claim["spec"]["timeout_s"] = timeout
    with pytest.raises(SpecError):
        resolve_spec(claim, "w1", str(tmp_path), 2.0)


def test_resolve_spec_missing_timeout_uses_default(tmp_path):
    claim = _claim()
    del claim["spec"]["timeout_s"]
    spec = resolve_spec(claim, "w1", str(tmp_path), 2.0, home=str(tmp_path))
    assert spec.timeout_s == 300.0


def test_resolve_spec_applies_claim_heartbeat_minimum(tmp_path):
    claim = _claim()
    claim["heartbeat_s"] = 0.5
    spec = resolve_spec(claim, "w1", str(tmp_path), 2.0, home=str(tmp_path))
    assert spec.heartbeat_s == 0.5


def test_resolve_spec_rejects_overlong_dispatch_id(tmp_path):
    with pytest.raises(SpecError):
        resolve_spec(_claim(dispatch_id="d" * 200), "w1", str(tmp_path), 2.0)


def test_resolve_spec_refuses_argv_carrying_spec(tmp_path):
    claim = _claim()
    claim["spec"]["argv"] = ["evil"]
    with pytest.raises(SpecError):
        resolve_spec(claim, "w1", str(tmp_path), 2.0)


def test_resolve_spec_refuses_unknown_adapter(tmp_path):
    claim = _claim()
    claim["spec"]["adapter"] = "shell"
    with pytest.raises(SpecError):
        resolve_spec(claim, "w1", str(tmp_path), 2.0)


@pytest.mark.parametrize("key", [None, "", "has space", 123, "k" * 201])
def test_resolve_spec_rejects_bad_effect_key(tmp_path, key):
    claim = _claim()
    claim["spec"]["effect_key"] = key
    with pytest.raises(SpecError):
        resolve_spec(claim, "w1", str(tmp_path), 2.0)


def test_resolve_spec_happy_path_identity(tmp_path):
    spec = resolve_spec(_claim(), "w9", str(tmp_path / "artifacts"), 2.0,
                        home=str(tmp_path))
    assert (spec.task_id, spec.dispatch_id, spec.worker_id) == ("t1", "d1", "w9")
    assert spec.result_id == "r-d1"
    assert spec.adapter == "synthetic"
    assert spec.effect_key == EFFECT_KEY
    assert spec.artifact_dir == os.path.join(str(tmp_path), "artifacts", "d1")

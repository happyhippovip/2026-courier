"""L4 synthetic adapter: deterministic execution + fail-closed verification.

Covers the WINDOW 6 requirements against the L2 verifier hand-off
(``verify(task, result, home)``): no external side effects, evidence before
acceptance, fail-closed rejects, duplicate/stale safety at the evidence layer
(controller journal owns fencing + dedupe), evidence preserved on rejection,
deterministic success + failure, fault injection, single source of truth
(read-only verifier, journal owns state).
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from adapters import synthetic
from adapters.synthetic import SyntheticCrash, SyntheticHang
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus, TaskState


def task(**changes):
    value = dict(task_id="t1", status=TaskStatus.VERIFYING, adapter="synthetic",
                 params={"write": "out.txt", "content": "courier-golden"},
                 effect_class="idempotent", max_attempts=3, lease_ttl_s=6,
                 timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def ready(payload, dispatch_id="d1"):
    return Event(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                 dispatch_id=dispatch_id, worker_id="w1", result_id="r1",
                 payload=payload)


def success_payload(workdir, name="out.txt", content="courier-golden"):
    digest = hashlib.sha256(content.encode()).hexdigest()
    return {"outcome": "success",
            "artifacts": [{"path": name, "sha256": digest}]}


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(root).rglob("*") if p.is_file()}


# -- execution: deterministic success ----------------------------------------

def test_run_writes_declared_content_atomically(tmp_path):
    res = synthetic.run({"write": "out.txt", "content": "courier-golden"}, tmp_path)
    assert res.outcome == "success"
    data = (tmp_path / "out.txt").read_bytes()
    assert data == b"courier-golden"
    assert res.artifacts == [{"path": "out.txt",
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data)}]


def test_run_is_deterministic(tmp_path):
    first = synthetic.run({"content": "abc"}, tmp_path / "a")
    second = synthetic.run({"content": "abc"}, tmp_path / "b")
    assert first.artifacts == second.artifacts


def test_run_writes_nothing_outside_workdir(tmp_path):
    (tmp_path / "sibling.txt").write_text("untouched")
    synthetic.run({"write": "sub/out.txt", "content": "x"}, tmp_path / "work")
    assert (tmp_path / "sibling.txt").read_text() == "untouched"
    assert (tmp_path / "work" / "sub" / "out.txt").read_text() == "x"


def test_run_rejects_unsafe_write_name(tmp_path):
    for bad in ("../evil.txt", "/abs.txt", "C:evil.txt", ""):
        with pytest.raises(synthetic.SyntheticError):
            synthetic.run({"write": bad, "content": "x"}, tmp_path)


def test_run_rejects_bad_params(tmp_path):
    with pytest.raises(synthetic.SyntheticError):
        synthetic.run({"sleep_s": -1}, tmp_path)
    with pytest.raises(synthetic.SyntheticError):
        synthetic.run({"fault_attempts": []}, tmp_path)
    with pytest.raises(synthetic.SyntheticError):
        synthetic.run("nope", tmp_path)


# -- execution: fault injection ------------------------------------------------

def test_transient_failure_then_success(tmp_path):
    params = {"fail_transient_n": 2, "content": "ok"}
    first = synthetic.run(params, tmp_path, attempt=1)
    second = synthetic.run(params, tmp_path, attempt=2)
    third = synthetic.run(params, tmp_path, attempt=3)
    assert (first.outcome, first.retryable) == ("failure", True)
    assert (second.outcome, second.retryable) == ("failure", True)
    assert third.outcome == "success"
    assert first.artifacts == []  # nothing produced yet: nothing to preserve


def test_crash_fault_only_on_listed_attempts(tmp_path):
    params = {"crash_after_s": 0, "fault_attempts": [1]}
    with pytest.raises(SyntheticCrash):
        synthetic.run(params, tmp_path, attempt=1)
    res = synthetic.run(params, tmp_path, attempt=2)
    assert res.outcome == "success"


def test_hang_fault_only_on_listed_attempts(tmp_path):
    params = {"hang": True, "fault_attempts": [2]}
    assert synthetic.run(params, tmp_path, attempt=1).outcome == "success"
    with pytest.raises(SyntheticHang):
        synthetic.run(params, tmp_path, attempt=2)


# -- verification: accept path -------------------------------------------------

def test_verify_accepts_run_output(tmp_path):
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    verdict = synthetic.verify(task(params=params), ready(success_payload(tmp_path)), tmp_path)
    assert verdict.accepted is True
    assert verdict.retryable is False
    assert verdict.verifier is None  # the controller stamps identity


def test_verify_accepts_shape_only_without_declared_content(tmp_path):
    (tmp_path / "free.txt").write_bytes(b"whatever")
    digest = hashlib.sha256(b"whatever").hexdigest()
    t = task(params={})
    verdict = synthetic.verify(t, ready({"outcome": "success",
                                         "artifacts": [{"path": "free.txt", "sha256": digest}]}), tmp_path)
    assert verdict.accepted is True


def test_verify_is_deterministic_and_side_effect_free(tmp_path):
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    payload = success_payload(tmp_path)
    before = snapshot(tmp_path)
    first = synthetic.verify(task(params=params), ready(payload), tmp_path)
    second = synthetic.verify(task(params=params), ready(payload), tmp_path)
    assert (first.accepted, first.reason) == (second.accepted, second.reason)
    assert snapshot(tmp_path) == before  # read-only: journal stays the only truth


# -- verification: failure outcomes --------------------------------------------

def test_verify_rejects_failure_with_payload_retryable(tmp_path):
    verdict = synthetic.verify(task(), ready({"outcome": "failure", "artifacts": [],
                                              "retryable": True, "reason": "boom"}), tmp_path)
    assert verdict.accepted is False and verdict.retryable is True


def test_verify_retryable_defaults_to_effect_class(tmp_path):
    payload = {"outcome": "failure", "artifacts": []}
    assert synthetic.verify(task(effect_class="idempotent"), ready(payload), tmp_path).retryable is True
    assert synthetic.verify(task(effect_class="non_idempotent"), ready(payload), tmp_path).retryable is False


# -- verification: empty / malformed evidence -----------------------------------

@pytest.mark.parametrize("artifacts", ["oops", [{"path": "out.txt"}], [{"sha256": "x"}],
                                       [{"path": "out.txt", "sha256": "not-hex"}],
                                       [{"path": "", "sha256": "0" * 64}]])
def test_malformed_evidence_never_reaches_verifier(tmp_path, artifacts):
    """Schema gate first: malformed shapes die at Event construction, so the
    verifier (and the journal) can never see them. Separate from the
    verifier's own rejects below, which handle schema-valid but bad evidence."""
    from courier_core.events import EventValidationError
    with pytest.raises(EventValidationError):
        ready({"outcome": "success", "artifacts": artifacts})


def test_verify_rejects_empty_evidence(tmp_path):
    verdict = synthetic.verify(task(), ready({"outcome": "success", "artifacts": []}), tmp_path)
    assert verdict.accepted is False


def test_verify_rejects_missing_file(tmp_path):
    digest = hashlib.sha256(b"courier-golden").hexdigest()
    verdict = synthetic.verify(task(), ready({"outcome": "success",
                                              "artifacts": [{"path": "out.txt", "sha256": digest}]}), tmp_path)
    assert verdict.accepted is False


def test_verify_rejects_tampered_bytes_but_preserves_them(tmp_path):
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    (tmp_path / "out.txt").write_bytes(b"tampered")
    verdict = synthetic.verify(task(params=params), ready(success_payload(tmp_path)), tmp_path)
    assert verdict.accepted is False
    assert (tmp_path / "out.txt").read_bytes() == b"tampered"  # preserved for inspection


def test_verify_rejects_content_mismatch_and_absent_declared_artifact(tmp_path):
    (tmp_path / "other.txt").write_bytes(b"zzz")
    digest = hashlib.sha256(b"zzz").hexdigest()
    payload = {"outcome": "success", "artifacts": [{"path": "other.txt", "sha256": digest}]}
    verdict = synthetic.verify(task(), ready(payload), tmp_path)
    assert verdict.accepted is False  # declared out.txt absent


@pytest.mark.parametrize("evil", ["../out.txt", "/etc/passwd", "C:evil.txt", "\\\\unc\\x"])
def test_verify_rejects_path_escapes(tmp_path, evil):
    (tmp_path / "out.txt").write_bytes(b"courier-golden")
    digest = hashlib.sha256(b"courier-golden").hexdigest()
    verdict = synthetic.verify(task(), ready({"outcome": "success",
                                              "artifacts": [{"path": evil, "sha256": digest}]}), tmp_path)
    assert verdict.accepted is False


def test_verify_never_raises_on_garbage(tmp_path):
    # Missing keys die at construction (schema requires payload keys upfront),
    # so the verifier can never be called on keyless garbage.
    from courier_core.events import EventValidationError
    with pytest.raises(EventValidationError):
        ready({})
    with pytest.raises(EventValidationError):
        ready({"outcome": "success"})
    # schema-valid but evidence-bad still rejects without raising (see above)


# -- evidence-layer duplicate / stale safety ------------------------------------

def test_verify_judges_evidence_only_for_superseded_attempt(tmp_path):
    """Staleness is the journal's job (fencing); the verifier is pure evidence.

    A superseded-attempt result with VALID evidence still verifies: it cannot
    move state because verify() writes nothing and the controller fences it to
    LATE_RESULT_DISCARDED. This test pins the separation."""
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    old = task(attempt=1)
    verdict = synthetic.verify(old, ready(success_payload(tmp_path)), tmp_path)
    assert verdict.accepted is True


def test_verify_rejects_foreign_dispatch(tmp_path):
    """Per-dispatch binding: sound bytes claimed for another dispatch never verify.

    The journal fences stale dispatches too, but verify() must not accept
    evidence bound elsewhere, no matter how sound the bytes are."""
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    verdict = synthetic.verify(task(params=params, dispatch_id="d-active"),
                               ready(success_payload(tmp_path), dispatch_id="d-other"),
                               tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert (tmp_path / "out.txt").read_bytes() == b"courier-golden"  # preserved


def test_verify_accepts_matching_dispatch(tmp_path):
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    verdict = synthetic.verify(task(params=params, dispatch_id="d1"),
                               ready(success_payload(tmp_path), dispatch_id="d1"),
                               tmp_path)
    assert verdict.accepted is True


def test_verdict_shape_matches_controller_contract(tmp_path):
    params = {"write": "out.txt", "content": "courier-golden"}
    synthetic.run(params, tmp_path)
    verdict = synthetic.verify(task(params=params), ready(success_payload(tmp_path)), tmp_path)
    assert isinstance(verdict.accepted, bool)
    assert isinstance(verdict.reason, str) and verdict.reason
    assert isinstance(verdict.retryable, bool)
    try:
        from courier_core.verification import Verdict
    except ImportError:
        Verdict = None
    if Verdict is not None:  # composed tree: isinstance gate in run_verifier passes
        assert isinstance(verdict, Verdict)


def test_run_result_json_round_trips_for_wire_use(tmp_path):
    res = synthetic.run({"content": "abc"}, tmp_path)
    wire = json.loads(json.dumps({"outcome": res.outcome, "artifacts": res.artifacts,
                                  "reason": res.reason, "retryable": res.retryable}))
    assert wire["artifacts"][0]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert os.path.isfile(tmp_path / "out.txt")


# -- worker host layout: artifacts/<dispatch_id>/<write> under home ------------
def test_verify_accepts_worker_host_per_dispatch_layout(tmp_path):
    out = synthetic.run({"write": "out.txt", "content": "courier-golden"}, tmp_path / "artifacts" / "d1")
    path = "artifacts/d1/" + out.artifacts[0]["path"]
    verdict = synthetic.verify(task(), ready({"outcome": "success",
                                              "artifacts": [{"path": path, "sha256": out.artifacts[0]["sha256"]}]}),
                               tmp_path)
    assert verdict.accepted is True, verdict.reason


def test_verify_pins_only_this_dispatch_directory(tmp_path):
    # Valid golden bytes, but in another dispatch's directory: never the pinned artifact.
    out = synthetic.run({"write": "out.txt", "content": "courier-golden"}, tmp_path / "artifacts" / "d-other")
    evidence = [{"path": "artifacts/d-other/out.txt", "sha256": out.artifacts[0]["sha256"]}]
    verdict = synthetic.verify(task(), ready({"outcome": "success", "artifacts": evidence}), tmp_path)
    assert verdict.accepted is False and "absent" in verdict.reason


def test_verify_malformed_dispatch_id_falls_back_to_plain_name(tmp_path):
    # A hostile dispatch_id must not broaden the pin: only the plain name counts.
    out = synthetic.run({"write": "out.txt", "content": "courier-golden"}, tmp_path)
    evil = Event(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                 dispatch_id="../evil", worker_id="w1", result_id="r1",
                 payload={"outcome": "success",
                          "artifacts": [{"path": "out.txt", "sha256": out.artifacts[0]["sha256"]}]})
    verdict = synthetic.verify(task(), evil, tmp_path)
    assert verdict.accepted is True, verdict.reason

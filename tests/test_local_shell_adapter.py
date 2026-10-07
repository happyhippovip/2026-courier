"""L4 local_shell adapter: bounded execution + fail-closed verification.

Covers the local_shell verifier against the L2 hand-off
(``verify(task, result, home)``): sandboxed execution with no shell,
kill-on-timeout, evidence before acceptance, fail-closed rejects,
duplicate/stale safety at the evidence layer (controller journal owns
fencing + dedupe), evidence preserved on rejection, and dynamic dispatch
plug-in (``adapters.local_shell.verify`` resolves with zero caller changes).
"""

import hashlib
import sys
from pathlib import Path

import pytest

from adapters import local_shell
from adapters.local_shell import LocalShellError, LocalShellTimeout
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus, TaskState
from courier_core.verification import adapter_verifier, run_verifier


def write_argv(text="shell-made"):
    return [sys.executable, "-c",
            "import sys; open('out.txt', 'w').write(sys.argv[1])", text]


def task(**changes):
    value = dict(task_id="t1", status=TaskStatus.VERIFYING, adapter="local_shell",
                 params={"command": write_argv(), "write": "out.txt"},
                 effect_class="idempotent", max_attempts=3, lease_ttl_s=6,
                 timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def ready(payload, dispatch_id="d1"):
    return Event(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                 dispatch_id=dispatch_id, worker_id="w1", result_id="r1",
                 payload=payload)


def success_payload(home, name="out.txt"):
    digest = hashlib.sha256((Path(home) / name).read_bytes()).hexdigest()
    return {"outcome": "success",
            "artifacts": [{"path": name, "sha256": digest}]}


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(root).rglob("*") if p.is_file()}


# -- execution: bounded success ------------------------------------------------

def test_run_executes_command_and_reports_evidence(tmp_path):
    res = local_shell.run({"command": write_argv("hello"), "write": "out.txt"},
                          tmp_path)
    assert res.outcome == "success"
    data = (tmp_path / "out.txt").read_bytes()
    assert data == b"hello"
    assert res.artifacts == [{"path": "out.txt",
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data)}]


def test_run_confines_relative_writes_to_workdir(tmp_path):
    (tmp_path / "sibling.txt").write_text("untouched")
    argv = [sys.executable, "-c", "open('sub/out.txt', 'w').write('x')"]
    (tmp_path / "work" / "sub").mkdir(parents=True)
    res = local_shell.run({"command": argv, "write": "sub/out.txt"},
                          tmp_path / "work")
    assert res.outcome == "success"
    assert (tmp_path / "sibling.txt").read_text() == "untouched"
    assert (tmp_path / "work" / "sub" / "out.txt").read_text() == "x"


def test_run_rejects_bad_params(tmp_path):
    with pytest.raises(LocalShellError):
        local_shell.run({"command": [], "write": "out.txt"}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run({"command": "not-a-list", "write": "out.txt"}, tmp_path)
    with pytest.raises(LocalShellError, match="null"):
        local_shell.run({"command": [sys.executable, "-c", "pass", "a\x00b"], "write": "out.txt"}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run({"command": write_argv(), "write": "../evil.txt"}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run({"command": write_argv(), "timeout_s": 0}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run({"command": write_argv(), "timeout_s": 601}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run({"command": write_argv(), "env": {"OK": 1}}, tmp_path)
    with pytest.raises(LocalShellError):
        local_shell.run("nope", tmp_path)


def test_run_rejects_bad_attempt(tmp_path):
    with pytest.raises(LocalShellError):
        local_shell.run({"command": write_argv()}, tmp_path, attempt=0)


# -- execution: failure + timeout ----------------------------------------------

def test_nonzero_exit_is_failure_without_evidence(tmp_path):
    argv = [sys.executable, "-c", "raise SystemExit(3)"]
    res = local_shell.run({"command": argv, "write": "out.txt"}, tmp_path)
    assert res.outcome == "failure"
    assert res.retryable is False
    assert "3" in res.reason
    assert res.artifacts == []
    assert not (tmp_path / "out.txt").exists()


def test_zero_exit_without_evidence_file_is_failure(tmp_path):
    argv = [sys.executable, "-c", "pass"]
    res = local_shell.run({"command": argv, "write": "out.txt"}, tmp_path)
    assert res.outcome == "failure"
    assert res.artifacts == []


def test_timeout_kills_and_raises(tmp_path):
    argv = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(LocalShellTimeout):
        local_shell.run({"command": argv, "write": "out.txt", "timeout_s": 0.2},
                        tmp_path)


def test_unstartable_command_is_param_error(tmp_path):
    argv = ["definitely-not-a-real-binary-xyz", "--version"]
    with pytest.raises(LocalShellError):
        local_shell.run({"command": argv, "write": "out.txt"}, tmp_path)


# -- verification: accept path ---------------------------------------------------

def test_verify_accepts_run_output(tmp_path):
    res = local_shell.run({"command": write_argv(), "write": "out.txt"}, tmp_path)
    verdict = local_shell.verify(task(), ready({"outcome": "success",
                                                "artifacts": res.artifacts}),
                                 tmp_path)
    assert verdict.accepted is True
    assert verdict.verifier is None  # run_verifier stamps identity, not the adapter


def test_dispatch_plugs_in_with_zero_caller_changes():
    assert adapter_verifier("local_shell") is local_shell.verify


def test_run_verifier_accepts_end_to_end(tmp_path):
    res = local_shell.run({"command": write_argv(), "write": "out.txt"}, tmp_path)
    verdict = run_verifier(adapter_verifier, task(),
                           ready({"outcome": "success",
                                  "artifacts": res.artifacts}, dispatch_id="d1"),
                           tmp_path)
    assert verdict.accepted is True
    assert verdict.verifier["name"].startswith("adapters.local_shell.")


# -- verification: fail-closed rejects ---------------------------------------------

def test_verify_rejects_failure_outcome(tmp_path):
    verdict = local_shell.verify(task(), ready({"outcome": "failure",
                                                "artifacts": [],
                                                "reason": "boom"}), tmp_path)
    assert verdict.accepted is False


def test_verify_rejects_dispatch_mismatch(tmp_path):
    local_shell.run({"command": write_argv(), "write": "out.txt"}, tmp_path)
    payload = success_payload(tmp_path)
    verdict = local_shell.verify(task(dispatch_id="d1"),
                                 ready(payload, dispatch_id="other"),
                                 tmp_path)
    assert verdict.accepted is False


def test_verify_rejects_empty_evidence(tmp_path):
    assert local_shell.verify(task(), ready({"outcome": "success",
                                             "artifacts": []}), tmp_path).accepted is False


@pytest.mark.parametrize("artifacts", ["oops", [{"path": "out.txt"}], [{"sha256": "x"}],
                                       [{"path": "out.txt", "sha256": "not-hex"}],
                                       [{"path": "", "sha256": "0" * 64}]])
def test_malformed_evidence_never_reaches_verifier(tmp_path, artifacts):
    """Schema gate first: malformed shapes die at Event construction, so the
    verifier (and the journal) can never see them. Separate from the
    verifier's own rejects, which handle schema-valid but bad evidence."""
    from courier_core.events import EventValidationError
    with pytest.raises(EventValidationError):
        ready({"outcome": "success", "artifacts": artifacts})


def test_verify_rejects_unsafe_paths(tmp_path):
    digest = hashlib.sha256(b"x").hexdigest()
    for bad in ("../evil.txt", "/abs.txt", "C:evil.txt"):
        payload = {"outcome": "success",
                   "artifacts": [{"path": bad, "sha256": digest}]}
        assert local_shell.verify(task(), ready(payload), tmp_path).accepted is False


def test_verify_rejects_tampered_and_missing_files(tmp_path):
    local_shell.run({"command": write_argv("orig"), "write": "out.txt"}, tmp_path)
    payload = success_payload(tmp_path)
    (tmp_path / "out.txt").write_bytes(b"tampered")
    assert local_shell.verify(task(), ready(payload), tmp_path).accepted is False
    (tmp_path / "out.txt").unlink()
    assert local_shell.verify(task(), ready(payload), tmp_path).accepted is False


def test_verify_never_raises_on_schema_valid_but_bad_input(tmp_path):
    garbage = ready({"outcome": "success",
                     "artifacts": [{"path": "out.txt", "sha256": "0" * 64}]})
    assert local_shell.verify(task(), garbage, tmp_path).accepted is False
    assert local_shell.verify("not-a-task", garbage, tmp_path).accepted is False


def test_rejection_preserves_evidence(tmp_path):
    local_shell.run({"command": write_argv("orig"), "write": "out.txt"}, tmp_path)
    before = snapshot(tmp_path)
    payload = success_payload(tmp_path)
    (tmp_path / "out.txt").write_bytes(b"tampered")
    verdict = local_shell.verify(task(), ready(payload), tmp_path)
    assert verdict.accepted is False
    after = snapshot(tmp_path)
    assert after == {str(Path("out.txt")): hashlib.sha256(b"tampered").hexdigest()}
    assert set(after) == set(before)

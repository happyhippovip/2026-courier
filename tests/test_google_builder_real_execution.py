"""Regression tests for the Google Builder real-execution boundary (PR #247).

The provider runner is replaced with a recorder, so these tests prove Courier-side
control flow only. They are NOT evidence of a real Google/Antigravity execution.
"""
import json
import sys
import subprocess
from types import SimpleNamespace

import pytest

from courier_core.work_packet import PacketQueue, PacketState, WorkPacket, evaluate_packet
import scripts.google_builder_worker as gbw
from scripts.run_antigravity_bridge import AntigravityHookRunner, AntigravityVisualStateTracker

SHA = "f425d3285611333d81cfffa263deebba186e398c"
SURFACE_OK = {"has_agy_cli": True, "authorized_mode": "CLI_ONLY"}
OK_VERIFY = [sys.executable, "-c", "import sys; sys.exit(0)"]
BAD_VERIFY = [sys.executable, "-c", "import sys; sys.exit(3)"]


class RecordingRunner:
    def __init__(self, returncode=0, stdout='{"result":"done"}', stderr=""):
        self.calls = []
        self.rc, self.out, self.err = returncode, stdout, stderr

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return SimpleNamespace(returncode=self.rc, stdout=self.out, stderr=self.err)


def _hooks(tmp_path):
    return AntigravityHookRunner(AntigravityVisualStateTracker(repo_dir=tmp_path))


def _packet(pid="pkt-g", state=PacketState.CURRENT, **payload):
    base = {"task_type": "google_agent_execute", "workkey": "WK-TEST-1",
            "instruction": "Add a docstring to foo()", "verify_command": OK_VERIFY}
    base.update(payload)
    return WorkPacket(id=pid, owner_id="google-mac", target_sha=SHA, state=state, payload=base)


# ---- TEST E: host overload -------------------------------------------------

@pytest.mark.parametrize("sample,reason", [
    ({"memory_percent": 88.7, "swap_percent": 10.0}, "HOST_MEMORY_PRESSURE"),
    ({"memory_percent": 50.0, "swap_percent": 91.2}, "HOST_SWAP_PRESSURE"),
    (None, "HOST_METRICS_UNAVAILABLE"),
])
def test_overloaded_host_refuses_heavy_admission(tmp_path, sample, reason):
    admitted, detail = gbw.host_capacity_admission(lambda: sample)
    assert admitted is False and detail["reason"] == reason
    assert gbw.is_host_safe(tmp_path, sampler=lambda: sample) is False


def test_calm_host_admits(tmp_path):
    assert gbw.is_host_safe(tmp_path, sampler=lambda: {"memory_percent": 40, "swap_percent": 5}) is True


def test_overloaded_host_never_invokes_provider(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    monkeypatch.chdir(tmp_path)
    queue = PacketQueue()
    queue.add_packet(_packet())
    records = gbw.run_google_builder_queue(queue, repo_dir=tmp_path, current_sha=SHA,
                                           host_safe=False, lock_dir=tmp_path / "locks")
    assert records == [] and runner.calls == []
    assert queue.packets["pkt-g"].state == PacketState.PARKED_BY_HOST


# ---- fail-closed verifier --------------------------------------------------

def test_unknown_task_type_fails_closed(tmp_path):
    pkt = _packet(task_type="something_new")
    res = gbw.execute_packet_code_or_test_work(pkt, tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == "FAILED"


def test_missing_workkey_is_unauthorized_and_provider_not_called(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    res = gbw.execute_packet_code_or_test_work(_packet(workkey=None), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == "FAILED" and runner.calls == []


def test_no_supported_interface_fails_honestly(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    res = gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), {"has_agy_cli": False, "authorized_mode": "X"})
    ev = json.loads((tmp_path / res["evidence_file"]).read_text())
    assert res["verdict"] == "FAILED" and "NO_SUPPORTED_GOOGLE_INTERFACE" in ev["error"]
    assert runner.calls == []


# ---- TEST A shape: supported CLI + independent verification ----------------

def test_agent_pass_requires_independent_verify(tmp_path, monkeypatch):
    runner = RecordingRunner(stdout='{"result":"mentions quota but succeeded"}')
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    res = gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == "PASS"
    argv, kwargs = runner.calls[0]
    assert argv[:3] == ["agy", "--print", "Add a docstring to foo()"]
    assert "--sandbox" in argv and "--output-format" in argv
    assert kwargs["cwd"] == tmp_path and kwargs["timeout"] > 0
    ev = json.loads((tmp_path / res["evidence_file"]).read_text())
    assert ev["workkey"] == "WK-TEST-1" and ev["verify_exit_code"] == 0
    assert ev["provider_invoked"] is True


def test_agent_success_but_verify_failure_is_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(gbw, "AGENT_RUNNER", RecordingRunner())
    res = gbw.execute_packet_code_or_test_work(_packet(verify_command=BAD_VERIFY), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == "FAILED"


def test_agent_success_without_verify_command_is_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(gbw, "AGENT_RUNNER", RecordingRunner())
    res = gbw.execute_packet_code_or_test_work(_packet(verify_command=None), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == "FAILED"


def test_agent_timeout_marks_effects_uncertain(tmp_path, monkeypatch):
    def boom(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
    monkeypatch.setattr(gbw, "AGENT_RUNNER", boom)
    res = gbw.execute_packet_code_or_test_work(_packet(), tmp_path, _hooks(tmp_path), SURFACE_OK)
    ev = json.loads((tmp_path / res["evidence_file"]).read_text())
    assert res["verdict"] == "FAILED" and ev["effects_uncertain"] is True


# ---- TEST F: human approval ------------------------------------------------

def test_human_approval_blocks_only_that_task_without_provider_call(tmp_path, monkeypatch):
    runner = RecordingRunner()
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    res = gbw.execute_packet_code_or_test_work(_packet(requires_human_approval=True), tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res["verdict"] == gbw.VERDICT_HUMAN_APPROVAL and runner.calls == []
    res2 = gbw.execute_packet_code_or_test_work(
        _packet(pid="pkt-approved", requires_human_approval=True, human_approval_ref="APPROVAL-1"),
        tmp_path, _hooks(tmp_path), SURFACE_OK)
    assert res2["verdict"] == "PASS" and len(runner.calls) == 1


# ---- TEST D: quota park, unrelated work continues, no blind retry ---------

def _queue_env(tmp_path, monkeypatch, runner):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gbw, "AGENT_RUNNER", runner)
    monkeypatch.setattr(gbw, "probe_integration_surface", lambda: dict(SURFACE_OK))
    monkeypatch.setattr("scripts.run_antigravity_bridge.PROCESSED_DIR", tmp_path / "events/processed")
    monkeypatch.setattr("scripts.run_antigravity_bridge.DECISIONS_DIR", tmp_path / "events/chief-decisions")


def test_quota_parks_affected_packet_and_unrelated_work_runs(tmp_path, monkeypatch):
    runner = RecordingRunner(returncode=1, stdout="", stderr="Error 429: RESOURCE_EXHAUSTED quota exceeded")
    _queue_env(tmp_path, monkeypatch, runner)
    (tmp_path / "b.txt").write_text("B", encoding="utf-8")
    queue = PacketQueue()
    queue.add_packet(_packet("pkt-google-a"))
    queue.add_packet(WorkPacket(id="pkt-indep-b", owner_id="google-mac", target_sha=SHA, state=PacketState.NEXT,
                                payload={"task_type": "verify_file", "target_file": "b.txt", "allowed_scope": ["b.txt"]}))

    records = gbw.run_google_builder_queue(queue, repo_dir=tmp_path, current_sha=SHA, max_units=5,
                                           host_safe=True, lock_dir=tmp_path / "locks")

    assert [r["packet_id"] for r in records] == ["pkt-google-a", "pkt-indep-b"]
    assert records[0]["decision"]["verdict"] == "PARKED"
    assert records[1]["decision"]["verdict"] == "ACCEPTED"
    assert queue.packets["pkt-google-a"].state == PacketState.PARKED_PROVIDER_LIMIT
    assert len(runner.calls) == 1  # no blind retry

    central = json.loads((tmp_path / "central_state.json").read_text())
    assert central["tasks"]["pkt-google-a"]["reconciled_status"] == gbw.VERDICT_PROVIDER_LIMIT

    # Host becoming safe again must NOT wake a provider-limit park.
    again = evaluate_packet(queue.packets["pkt-google-a"], SHA, host_safe=True)
    assert again.state == PacketState.PARKED_PROVIDER_LIMIT
    assert gbw.resume_provider_parked_packets(queue, provider_available=False) == []
    assert gbw.resume_provider_parked_packets(queue, provider_available=True) == ["pkt-google-a"]
    assert queue.packets["pkt-google-a"].state == PacketState.NEXT


def test_human_block_is_never_released_by_provider_signal(tmp_path, monkeypatch):
    runner = RecordingRunner()
    _queue_env(tmp_path, monkeypatch, runner)
    queue = PacketQueue()
    queue.add_packet(_packet("pkt-human", requires_human_approval=True))
    gbw.run_google_builder_queue(queue, repo_dir=tmp_path, current_sha=SHA, host_safe=True, lock_dir=tmp_path / "locks")
    assert queue.packets["pkt-human"].state == PacketState.BLOCKED_HUMAN_APPROVAL
    assert gbw.resume_provider_parked_packets(queue, provider_available=True) == []
    assert runner.calls == []


def test_sha_drift_supersedes_sticky_park():
    p = _packet(state=PacketState.PARKED_PROVIDER_LIMIT)
    assert evaluate_packet(p, "other-sha", host_safe=True).state == PacketState.SUPERSEDED

import json
import sys
import time

import pytest

from scripts.provider_hub import hub as hub_module
from scripts.provider_hub.hub import DispatcherLock, ProviderHub, classify, redact, scopes_overlap
from scripts.windows_muse_wall.slot_state import atomic_write

CONFIG = {
    "default_effort": "medium",
    "poll_seconds": 0.05,
    "slots": [
        {"slot_id": "G1", "provider": "google", "account": "a1"},
        {"slot_id": "G2", "provider": "google", "account": "a1", "profile_home": "X"},
        {"slot_id": "M1", "provider": "muse", "account": "m1"},
    ],
}


class FakeHub(ProviderHub):
    """Replaces provider binaries with a python child that sleeps, then echoes."""

    sleep = 0.4

    def command(self, slot, job):
        code = f"import time; time.sleep({self.sleep}); print('ok ' + {job['prompt']!r})"
        return [sys.executable, "-c", code]


def make(tmp_path, cls=FakeHub):
    return cls(root=tmp_path / "rt", config=json.loads(json.dumps(CONFIG)))


def states(hub):
    return {job["job_id"]: job["state"] for job in hub.jobs()}


def test_one_job_per_slot_and_queue_waits(tmp_path):
    hub = make(tmp_path)
    jobs = [hub.submit("google", f"p{i}") for i in range(3)]
    hub.tick()
    running = [job for job in hub.jobs() if job["state"] == "RUNNING"]
    assert {job["slot_id"] for job in running} == {"G1", "G2"}
    assert hub.jobs()[2]["state"] == "QUEUED"
    hub.run(until_idle=True, max_seconds=20)
    assert set(states(hub).values()) == {"DONE"}
    assert jobs[2]["job_id"] in states(hub)


def test_overlapping_write_scopes_never_run_together(tmp_path):
    hub = make(tmp_path)
    scope = tmp_path / "repo"
    first = hub.submit("google", "a", write_scope=scope)
    second = hub.submit("google", "b", write_scope=scope / "sub")
    hub.tick()
    assert states(hub) == {first["job_id"]: "RUNNING", second["job_id"]: "QUEUED"}
    hub.run(until_idle=True, max_seconds=20)
    done = {job["job_id"]: job for job in hub.jobs()}
    assert done[second["job_id"]]["started_at"] >= done[first["job_id"]]["finished_at"]


def test_scope_overlap_rules(tmp_path):
    assert scopes_overlap(tmp_path / "a", tmp_path / "a" / "b")
    assert not scopes_overlap(tmp_path / "a", tmp_path / "ab")
    assert not scopes_overlap(None, tmp_path)


def test_expensive_effort_rejected(tmp_path):
    hub = make(tmp_path)
    for effort in ("xhigh", "max", "ultra"):
        with pytest.raises(ValueError):
            hub.submit("muse", "x", effort=effort)
    assert hub.jobs() == []


def test_unhealthy_slot_is_skipped(tmp_path):
    hub = make(tmp_path)
    atomic_write(hub.slots_dir / "G1.health.json", {"state": "AUTH_REQUIRED"})
    job = hub.submit("google", "x")
    hub.tick()
    assert hub.jobs()[0]["slot_id"] == "G2"
    hub.run(until_idle=True, max_seconds=20)
    assert states(hub)[job["job_id"]] == "DONE"


def test_second_dispatcher_refused_and_stale_lock_reclaimed(tmp_path):
    path = tmp_path / "hub.lock"
    with DispatcherLock(path):
        with pytest.raises(RuntimeError):
            DispatcherLock(path).__enter__()
    atomic_write(path, {"pid": 999999, "create_time": 1.0})
    with DispatcherLock(path):
        assert path.exists()
    assert not path.exists()


def test_events_have_fields_and_no_secrets(tmp_path):
    hub = make(tmp_path)
    hub.submit("muse", "token=ya29.SECRETVALUE123 api_key: sk-abcdefghijklmnopqrstu")
    hub.run(until_idle=True, max_seconds=20)
    lines = hub.events_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert [r["state"] for r in records] == ["QUEUED", "RUNNING", "DONE"]
    for field in ("provider", "slot", "job", "start", "state", "result", "error"):
        assert field in records[-1]
    assert records[-1]["slot"] == "M1"
    blob = "\n".join(lines)
    assert "SECRETVALUE" not in blob and "sk-abc" not in blob
    assert "prompt" not in records[-1]


def test_timeout_kills_exact_process(tmp_path):
    hub = make(tmp_path)
    FakeHub.sleep = 30
    try:
        job = hub.submit("google", "slow", timeout_s=0)
        hub.tick()
        running = hub.jobs()[0]
        running["started_at"] = time.time() - 120
        atomic_write(hub.job_path(job["job_id"]), running)
        hub.tick()
        final = hub.jobs()[0]
        assert final["state"] == "FAILED" and final["error"] == "timeout"
    finally:
        FakeHub.sleep = 0.4


def test_classify_health():
    assert classify(0, "HUBPONG", "") == "READY"
    assert classify(1, "", "Please log in to continue") == "AUTH_REQUIRED"
    assert classify(1, "", "RESOURCE_EXHAUSTED") == "QUOTA"
    assert classify(1, "", "certificate has expired") == "EXPIRED"
    assert classify(None, "", "", timed_out=True) == "UNKNOWN"
    assert classify(1, "", "boom") == "BROKEN"


def test_real_commands_never_use_unsafe_flags(tmp_path, monkeypatch):
    hub = ProviderHub(root=tmp_path / "rt", config=json.loads(json.dumps(CONFIG)))
    monkeypatch.setattr(hub_module, "muse_binary", lambda: "muse-bin.exe")
    job = {"prompt": "p", "effort": "medium", "timeout_s": 60, "write_scope": None, "workdir": str(tmp_path)}
    for slot in hub.slots.values():
        argv = hub.command(slot, job)
        assert "--yolo" not in argv and "--dangerously-skip-permissions" not in argv
    assert redact("Bearer abc.def token=xyz") .count("<redacted>") >= 1

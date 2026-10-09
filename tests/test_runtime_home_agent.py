import json

from courier_runtime.home_agent import HomeAgent, LocalGrants, default_handlers, submit, why_refused


def agent(tmp_path, grants=LocalGrants(), handlers=None):
    calls = []
    h = handlers or {a: (lambda p, a=a: calls.append(a) or {"ok": a}) for a in
                     ("host_health", "surface_status", "reclaim_idle_surfaces", "git_pull_repo")}
    return HomeAgent(tmp_path / "mailbox", "pc-1", grants, h, clock=lambda: 5.0), calls


def test_read_actions_run_by_default_and_only_once(tmp_path):
    a, calls = agent(tmp_path)
    submit(tmp_path / "mailbox", "pc-1", "job1", "host_health")
    submit(tmp_path / "mailbox", "pc-1", "job1", "host_health")        # duplicate submit = same job
    first, second = a.run_once(), a.run_once()
    assert [r["status"] for r in first] == ["DONE"] and second == [] and calls == ["host_health"]
    receipt = json.loads((tmp_path / "mailbox/pc-1/outbox/job1.json").read_text())
    assert receipt["result"] == {"ok": "host_health"} and receipt["host"] == "pc-1"


def test_repo_content_cannot_grant_itself_more(tmp_path):
    a, calls = agent(tmp_path)                                          # default: read only
    submit(tmp_path / "mailbox", "pc-1", "j", "reclaim_idle_surfaces")
    (tmp_path / "mailbox/pc-1/inbox/j2.json").write_text(json.dumps(
        {"action": "reclaim_idle_surfaces", "grants": {"max_access": "control"}}))   # tries to self-grant
    assert [r["status"] for r in a.run_once()] == ["REFUSED", "REFUSED"] and calls == []


def test_no_free_commands_ever(tmp_path):
    g = LocalGrants(max_access="control", allowed_actions=frozenset({"host_health"}))
    assert "only catalog actions" in why_refused({"action": "shell"}, g)
    assert why_refused({"action": "host_health", "argv": ["rm", "-rf", "/"]}, g) == "jobs may not carry commands"


def test_local_grants_allow_more_and_pause_stops_all(tmp_path):
    gpath = tmp_path / "home_grants.json"
    gpath.write_text(json.dumps({"max_access": "write", "allowed_actions": ["host_health", "git_pull_repo"],
                                 "allowed_repos": ["/repos/courier"]}))
    g = LocalGrants.load(gpath)
    assert why_refused({"action": "git_pull_repo", "params": {"repo": "/repos/courier"}}, g) is None
    assert "allowlist" in why_refused({"action": "git_pull_repo", "params": {"repo": "/etc"}}, g)
    assert "needs control" in why_refused({"action": "reclaim_idle_surfaces"},
                                           LocalGrants("write", frozenset({"reclaim_idle_surfaces"})))
    assert why_refused({"action": "host_health"}, LocalGrants(paused=True)) == "home agent is paused by the owner"
    assert LocalGrants.load(tmp_path / "missing.json") == LocalGrants()   # no file = read-only


def test_failures_and_garbage_are_reported_not_hidden(tmp_path):
    def boom(_):
        raise RuntimeError("disk gone")
    a, _ = agent(tmp_path, handlers={"host_health": boom})
    submit(tmp_path / "mailbox", "pc-1", "j1", "host_health")
    (tmp_path / "mailbox/pc-1/inbox/j2.json").write_text("{not json")
    r = {x["job_id"]: x for x in a.run_once()}
    assert r["j1"]["status"] == "FAILED" and "disk gone" in r["j1"]["reason"]
    assert r["j2"]["status"] == "REFUSED"


def test_real_host_health_handler_runs(tmp_path):
    a = HomeAgent(tmp_path / "mailbox", "pc-1", LocalGrants(), default_handlers())
    submit(tmp_path / "mailbox", "pc-1", "h1", "host_health")
    [r] = a.run_once()
    assert r["status"] == "DONE" and "findings" in r["result"] and r["result"]["uptime_min"] >= 0


def test_cli_once_against_a_git_mailbox(tmp_path):
    import subprocess

    from courier_runtime.home_agent import main
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    for k, v in (("user.email", "t@example.invalid"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(work), "config", k, v], check=True)
    submit(work / "mailbox", "pc-1", "h1", "surface_status")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-qm", "job"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "HEAD"], check=True, capture_output=True)
    assert main(["--repo", str(work), "--host", "pc-1", "--home", str(tmp_path / "home"), "--once"]) == 0
    receipt = json.loads((work / "mailbox/pc-1/outbox/h1.json").read_text())
    assert receipt["status"] == "DONE"
    log = subprocess.run(["git", "-C", str(remote), "log", "--oneline", "-1"], capture_output=True, text=True).stdout
    assert "home-agent pc-1: 1 receipt" in log


def _lock_record(pid):
    return {"pid": pid, "create_time": 1.0, "workkey": "home-agent",
            "owner": "courier", "recorded_at": 0.0}


def test_single_instance_denied_lock_is_not_taken_over(tmp_path, monkeypatch):
    """Access denial is not proof of exit: an unreadable lock holder may
    still be alive (e.g. another user), so the lock must stay untouched."""
    import psutil

    from courier_runtime.home_agent import _single_instance
    lock = tmp_path / "agent.lock"
    before = _lock_record(999991)
    lock.write_text(json.dumps(before))

    real_process = psutil.Process

    def denied(pid):
        if pid == before["pid"]:
            raise psutil.AccessDenied(pid)
        return real_process(pid)

    monkeypatch.setattr(psutil, "Process", denied)
    assert _single_instance(str(lock)) is False
    assert json.loads(lock.read_text()) == before


def test_single_instance_attr_denial_is_not_taken_over(tmp_path, monkeypatch):
    """Denial can surface on attribute access while construction succeeds
    (the common POSIX shape): still fence, still untouched."""
    import psutil

    from courier_runtime.home_agent import _single_instance
    lock = tmp_path / "agent.lock"
    before = _lock_record(999991)
    lock.write_text(json.dumps(before))
    real_process = psutil.Process

    class AttrDenied:
        def __init__(self, pid):
            self._pid = pid

        def status(self):
            return "running"  # basic state readable; identity detail is not

        def create_time(self):
            raise psutil.AccessDenied(self._pid)

    def selective(pid):
        if pid == before["pid"]:
            return AttrDenied(pid)
        return real_process(pid)

    monkeypatch.setattr(psutil, "Process", selective)
    assert _single_instance(str(lock)) is False
    assert json.loads(lock.read_text()) == before


def test_single_instance_dead_lock_is_taken_over(tmp_path, monkeypatch):
    """A provably dead holder (NoSuchProcess) keeps the documented takeover."""
    import os

    import psutil

    from courier_runtime.home_agent import _single_instance
    lock = tmp_path / "agent.lock"
    lock.write_text(json.dumps(_lock_record(999991)))

    real_process = psutil.Process

    def gone(pid):
        if pid == 999991:
            raise psutil.NoSuchProcess(pid)
        return real_process(pid)

    monkeypatch.setattr(psutil, "Process", gone)
    assert _single_instance(str(lock)) is True
    after = json.loads(lock.read_text())
    assert after["pid"] == os.getpid() and after["workkey"] == "home-agent"

"""Offline host loop. Fake providers and a fake GitHub view. No network."""

import json
import os
import stat
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from courier_core.work_queue import DEFAULT_ITEMS, WorkQueue
from courier_worker import host_loop
from courier_worker.adapters import provider_exec
from scripts.resource_governor import governor as live_governor

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _admit_heavy(monkeypatch):
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)


class Governor:
    def __init__(self, pressure="GREEN"):
        self.pressure = pressure
        self.admit_calls = 0

    def measure_pressure(self):
        if isinstance(self.pressure, BaseException):
            raise self.pressure
        return self.pressure

    def admit_job(self, budget):
        self.admit_calls += 1
        return True


class GitHub:
    def __init__(self, paths=None, done=None, branch=True, draft=True):
        self.paths = [] if paths is None else list(paths)
        self.done = [] if done is None else list(done)
        self.branch = branch
        self.draft = draft
        self.draft_calls = []

    def open_pr_paths(self):
        return list(self.paths)

    def done_prs(self):
        return list(self.done)

    def branch_exists(self, branch):
        if self.branch is True:
            return True
        if self.branch is False:
            return False
        return branch in self.branch

    def draft_pr(self, branch):
        self.draft_calls.append(branch)
        if self.draft is True:
            return ("https://example.invalid/pr/" + branch, "abc123def456")
        if self.draft is False or self.draft is None:
            return None
        return self.draft.get(branch)


def _item(item_id, scope, status="READY", depends=None):
    return {
        "id": item_id,
        "title": "Item " + item_id,
        "lane": "L2",
        "branch": "lane/L2-" + item_id,
        "files_scope": scope,
        "depends_on": depends or [],
        "acceptance": ["tests", "draft PR"],
        "provider_hints": ["headless"],
        "status": status,
        "lease": None,
    }


def _write_items(directory, rows):
    directory.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (directory / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")


def _fake(path: Path, mode: str, argv_log: Path, count_file: Path) -> str:
    path.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, sys, time
        from pathlib import Path
        forbidden = ("--yolo", "--disable-sandbox", "--dangerously-skip-permissions")
        if any(arg in forbidden for arg in sys.argv[1:]):
            sys.stderr.buffer.write(b"forbidden\\n")
            raise SystemExit(97)
        argv_log = Path({str(argv_log)!r})
        argv_log.parent.mkdir(parents=True, exist_ok=True)
        with argv_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sys.argv[1:]) + "\\n")
        count = Path({str(count_file)!r})
        current = int(count.read_text()) if count.exists() else 0
        count.write_text(str(current + 1))
        mode = {mode!r}
        if mode == "timeout":
            time.sleep(30)
        if mode == "crash":
            raise SystemExit(2)
        if mode == "refused":
            sys.stdout.buffer.write(b"refused to write; no-op\\n")
            raise SystemExit(0)
        if mode == "agy-deny":
            sys.stderr.buffer.write(b"approval refused\\n")
            sys.stdout.buffer.write(b'{{"status":"SUCCESS"}}\\n')
            raise SystemExit(0)
        if mode == "agy":
            sys.stdout.buffer.write(b'{{"status":"SUCCESS","response":"SECRET","usage":{{}}}}\\n')
            raise SystemExit(0)
        sys.stdout.buffer.write(b"provider-ok\\n")
        raise SystemExit(0)
        """), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
    return str(path.resolve())


def _config(tmp_path, items, binaries, **extra):
    home = extra.pop("home", None) or (tmp_path / "home")
    home.mkdir(parents=True, exist_ok=True)
    body = {
        "holder": extra.pop("holder", "holder-a"),
        "host": extra.pop("host", "host-a"),
        "home": str(home),
        "providers": extra.pop("providers", ["agy"]),
        "binaries": binaries,
        "timeout_s": extra.pop("timeout_s", 30),
        "lease_ttl_s": extra.pop("lease_ttl_s", 3600),
        "ledger": str(extra.pop("ledger", tmp_path / "queue.jsonl")),
        "items_dir": str(items),
        "tests_command": extra.pop("tests_command", ["python", "-c", "raise SystemExit(0)"]),
    }
    body.update(extra)
    path = home / "host.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path, home


def _events(ledger: Path):
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def _count(path: Path) -> int:
    if not path.exists():
        return 0
    return int(path.read_text(encoding="utf-8") or "0")


def _argv(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run(cfg, github, *mode, **kw):
    flags = list(mode) or ["--once"]
    return host_loop.main(
        [*flags, "--host-config", str(cfg)],
        github=github,
        governor=kw.get("governor", Governor()),
        now=kw.get("now", lambda: NOW),
        tests_runner=kw.get("tests_runner", lambda argv, workdir: 0),
        sleep=kw.get("sleep"),
        hooks=kw.get("hooks"),
        max_ticks=kw.get("max_ticks"),
        until_idle=kw.get("until_idle", False),
    )


def _layout(tmp_path, mode="agy", providers=None, rows=None, **extra):
    items = tmp_path / "items"
    _write_items(items, rows or [_item("A", ["docs/a.md"])])
    argv_log = tmp_path / "argv.jsonl"
    count = tmp_path / "count.txt"
    binary = _fake(tmp_path / "fake.py", mode, argv_log, count)
    name = (providers or ["agy"])[0]
    binaries = {name: binary}
    if extra.get("binaries"):
        binaries = extra.pop("binaries")
    cfg, home = _config(
        tmp_path, items, binaries, providers=providers or ["agy"], **extra,
    )
    return {
        "cfg": cfg, "home": home, "items": items, "argv": argv_log, "count": count,
        "ledger": Path(json.loads(cfg.read_text())["ledger"]), "binary": binary,
    }


def test_success_records_one_receipt_and_sandbox_argv(tmp_path):
    env = _layout(tmp_path, mode="agy")
    github = GitHub()
    calls = []
    code = _run(env["cfg"], github, tests_runner=lambda argv, workdir: calls.append(argv) or 0)
    assert code == 0
    assert calls == [["python", "-c", "raise SystemExit(0)"]]
    events = _events(env["ledger"])
    assert [event["type"] for event in events] == ["CLAIM", "RELEASE"]
    assert events[0]["holder"] == "holder-a"
    assert events[1]["result"].startswith("ACCEPTED provider=agy ")
    assert "pr=https://example.invalid/pr/lane/L2-A" in events[1]["result"]
    assert "head=abc123def456" in events[1]["result"]
    assert "tests=tests_exit=0" in events[1]["result"]
    assert "Item A" not in events[1]["result"]
    assert "SECRET" not in env["ledger"].read_text(encoding="utf-8")
    receipt = (env["home"] / "run" / "host_loop_receipts.jsonl").read_text(encoding="utf-8")
    assert "Item A" not in receipt and "SECRET" not in receipt
    argv = _argv(env["argv"])[0]
    assert "--sandbox" in argv
    assert "--yolo" not in argv
    assert "--dangerously-skip-permissions" not in argv
    assert "--disable-sandbox" not in argv
    assert host_loop.build_provider_params("agy", "id: A", 30) == {
        "provider": "agy", "prompt": "id: A", "timeout_s": 30,
    }
    again = _run(env["cfg"], github)
    assert again == 0
    assert [event["type"] for event in _events(env["ledger"])] == ["CLAIM", "RELEASE"]
    assert _count(env["count"]) == 1


def test_refused_exit_zero_is_failed_without_running_tests(tmp_path):
    env = _layout(tmp_path, mode="refused", providers=["muse"])
    calls = []
    github = GitHub()
    code = _run(env["cfg"], github, tests_runner=lambda argv, workdir: calls.append(1) or 0)
    assert code == 0 and calls == []
    release = _events(env["ledger"])[-1]
    assert release["type"] == "RELEASE"
    assert release["result"].startswith("FAILED provider=muse ")
    assert "blocker=REFUSED_OUTPUT" in release["result"]
    assert WorkQueue(env["items"], env["ledger"]).list_ready(now=NOW) == []


def test_timeout_and_crash_are_failed(tmp_path):
    timed = _layout(tmp_path / "timeout", mode="timeout", providers=["muse"], timeout_s=1)
    assert _run(timed["cfg"], GitHub()) == 0
    assert "blocker=TIMEOUT" in _events(timed["ledger"])[-1]["result"]
    assert _count(timed["count"]) == 1
    crashed = _layout(tmp_path / "crash", mode="crash", providers=["muse"])
    assert _run(crashed["cfg"], GitHub()) == 0
    assert "blocker=NONZERO_EXIT" in _events(crashed["ledger"])[-1]["result"]


def test_tests_and_github_failures(tmp_path):
    env = _layout(tmp_path / "tests", mode="agy")
    code = _run(env["cfg"], GitHub(), tests_runner=lambda argv, workdir: 1)
    assert code == 0
    assert "blocker=TESTS_FAILED" in _events(env["ledger"])[-1]["result"]
    assert "tests=tests_exit=1" in _events(env["ledger"])[-1]["result"]

    missing_branch = _layout(tmp_path / "branch", mode="agy")
    github = GitHub(branch=False)
    assert _run(missing_branch["cfg"], github) == 0
    assert "blocker=BRANCH_MISSING" in _events(missing_branch["ledger"])[-1]["result"]
    assert github.draft_calls == []

    missing_pr = _layout(tmp_path / "pr", mode="agy")
    github = GitHub(draft=False)
    assert _run(missing_pr["cfg"], github) == 0
    assert "blocker=PR_MISSING" in _events(missing_pr["ledger"])[-1]["result"]


def test_approval_refusal_blocks_item_and_does_not_try_the_next_provider(tmp_path):
    items = tmp_path / "items"
    _write_items(items, [_item("A", ["docs/a.md"]), _item("B", ["docs/b.md"])])
    agy_count = tmp_path / "agy.txt"
    muse_count = tmp_path / "muse.txt"
    agy = _fake(tmp_path / "agy.py", "agy-deny", tmp_path / "agy-argv.jsonl", agy_count)
    muse = _fake(tmp_path / "muse.py", "muse", tmp_path / "muse-argv.jsonl", muse_count)
    cfg, home = _config(tmp_path, items, {"agy": agy, "muse": muse}, providers=["agy", "muse"])
    assert _run(cfg, GitHub()) == 0
    assert _count(agy_count) == 1 and _count(muse_count) == 0
    result = _events(tmp_path / "queue.jsonl")[-1]["result"]
    assert result.startswith("BLOCKED provider=agy ")
    assert "blocker=PROVIDER_APPROVAL_REFUSED" in result
    state = json.loads((home / "host_loop_state.json").read_text(encoding="utf-8"))
    assert state["consecutive_all_failed"] == 0
    assert state["host_status"] == "READY"
    ready = [item["id"] for item in WorkQueue(items, tmp_path / "queue.jsonl").list_ready(now=NOW)]
    assert ready == ["B"]


def test_open_pr_paths_and_done_prs_are_passed_to_the_queue(tmp_path, monkeypatch):
    ledger = tmp_path / "queue.jsonl"
    cfg, home = _config(
        tmp_path, DEFAULT_ITEMS,
        {"agy": _fake(tmp_path / "agy.py", "agy", tmp_path / "argv.jsonl", tmp_path / "count.txt")},
        ledger=ledger,
    )
    seen = {}
    real_ready = host_loop.list_ready

    def spy(queue, open_pr_files=None, done_prs=None, now=None):
        seen["paths"] = list(open_pr_files or [])
        seen["done"] = list(done_prs or [])
        return real_ready(queue, open_pr_files=open_pr_files, done_prs=done_prs, now=now)

    github = GitHub(paths=["courier_core/result_digest.py"], done=["277"])
    monkeypatch.setattr(host_loop, "list_ready", spy)
    assert _run(cfg, github) == 0
    assert seen["paths"] == ["courier_core/result_digest.py"]
    assert seen["done"] == ["277"]
    claim = next(event for event in _events(ledger) if event["type"] == "CLAIM")
    assert claim["item_id"] == "P3"
    assert "Item " not in claim.get("result", "")

    gated = tmp_path / "gated"
    items = gated / "items"
    _write_items(items, [_item("B", ["docs/b.md"], depends=["277"])])
    binary = _fake(gated / "agy.py", "agy", gated / "argv.jsonl", gated / "count.txt")
    waiting, _home = _config(gated, items, {"agy": binary}, ledger=gated / "queue.jsonl")
    assert _run(waiting, GitHub(done=[])) == 0
    assert _events(gated / "queue.jsonl") == []
    assert _run(waiting, GitHub(done=["277"])) == 0
    assert _events(gated / "queue.jsonl")[0]["item_id"] == "B"


def test_unknown_github_and_unknown_governor_do_not_claim(tmp_path):
    env = _layout(tmp_path / "gh")

    class Unknown:
        def open_pr_paths(self):
            return None

        def done_prs(self):
            return []

        def branch_exists(self, branch):
            return True

        def draft_pr(self, branch):
            return ("https://example.invalid/pr", "abc")

    assert _run(env["cfg"], Unknown()) == 0
    assert _events(env["ledger"]) == []

    env = _layout(tmp_path / "gov")
    governor = Governor("UNKNOWN")
    assert _run(env["cfg"], GitHub(), governor=governor) == 0
    assert governor.admit_calls == 0
    assert _events(env["ledger"]) == []
    boom = Governor(RuntimeError("sensors"))
    assert _run(env["cfg"], GitHub(), governor=boom) == 0
    assert _events(env["ledger"]) == []


def test_live_governor_is_read_only(tmp_path, monkeypatch):
    env = _layout(tmp_path)
    calls = []
    live_governor.recovery_end_time = 0
    monkeypatch.setattr(live_governor, "measure_pressure", lambda: "GREEN")
    monkeypatch.setattr(live_governor, "admit_job", lambda budget: calls.append(budget) or True)
    assert _run(env["cfg"], GitHub(), governor=None) == 0
    assert calls == []
    assert _events(env["ledger"])[0]["type"] == "CLAIM"
    monkeypatch.setattr(live_governor, "measure_pressure", lambda: "RED")
    env = _layout(tmp_path / "red")
    assert _run(env["cfg"], GitHub(), governor=None) == 0
    assert _events(env["ledger"]) == []


def test_stop_and_pause(tmp_path):
    env = _layout(tmp_path / "stop")
    (env["home"] / "STOP").write_text("\n", encoding="utf-8")
    assert _run(env["cfg"], GitHub()) == 0
    assert _events(env["ledger"]) == []

    env = _layout(tmp_path / "pause")
    (env["home"] / "PAUSE").write_text("\n", encoding="utf-8")
    assert _run(env["cfg"], GitHub()) == 0
    assert _events(env["ledger"]) == []

    env = _layout(tmp_path / "resume")
    with pytest.raises(RuntimeError, match="after_claim"):
        _run(env["cfg"], GitHub(), hooks={"after_claim": lambda: (_ for _ in ()).throw(RuntimeError("after_claim"))})
    assert _count(env["count"]) == 0
    (env["home"] / "PAUSE").write_text("\n", encoding="utf-8")
    assert _run(env["cfg"], GitHub()) == 0
    assert _count(env["count"]) == 1
    assert [event["type"] for event in _events(env["ledger"])] == ["CLAIM", "RELEASE"]


def test_stop_after_claim_does_not_launch(tmp_path):
    env = _layout(tmp_path)
    with pytest.raises(RuntimeError):
        _run(env["cfg"], GitHub(), hooks={"after_claim": lambda: (_ for _ in ()).throw(RuntimeError("stop"))})
    (env["home"] / "STOP").write_text("\n", encoding="utf-8")
    assert _run(env["cfg"], GitHub()) == 0
    assert _count(env["count"]) == 0
    assert [event["type"] for event in _events(env["ledger"])] == ["CLAIM"]


def test_empty_queue_backoff_and_one_claim_at_a_time(tmp_path):
    items = tmp_path / "items"
    _write_items(items, [_item("Z", ["docs/z.md"], status="DONE")])
    binary = _fake(tmp_path / "agy.py", "agy", tmp_path / "argv.jsonl", tmp_path / "count.txt")
    cfg, _home = _config(tmp_path, items, {"agy": binary})
    slept = []
    assert _run(cfg, GitHub(), "--once", sleep=slept.append) == 0
    assert slept == []
    assert _run(cfg, GitHub(), "--forever", sleep=slept.append, max_ticks=2) == 0
    assert slept == [5, 10]

    pair = tmp_path / "pair"
    rows = [_item("A", ["docs/a.md"]), _item("B", ["docs/b.md"])]
    _write_items(pair / "items", rows)
    binary = _fake(pair / "agy.py", "agy", pair / "argv.jsonl", pair / "count.txt")
    cfg, home = _config(pair, pair / "items", {"agy": binary}, ledger=pair / "queue.jsonl")
    with pytest.raises(RuntimeError):
        _run(cfg, GitHub(), hooks={"after_claim": lambda: (_ for _ in ()).throw(RuntimeError("held"))})
    assert [event["item_id"] for event in _events(pair / "queue.jsonl")] == ["A"]
    assert _run(cfg, GitHub()) == 0
    assert [event["item_id"] for event in _events(pair / "queue.jsonl") if event["type"] == "CLAIM"] == ["A"]
    assert _run(cfg, GitHub()) == 0
    assert [event["item_id"] for event in _events(pair / "queue.jsonl") if event["type"] == "CLAIM"] == ["A", "B"]
    assert json.loads((home / "host_loop_state.json").read_text(encoding="utf-8"))["in_flight"] is None


def test_two_hosts_and_lease_expiry(tmp_path):
    items = tmp_path / "items"
    _write_items(items, [_item("A", ["docs/a.md"])])
    ledger = tmp_path / "queue.jsonl"
    binary = _fake(tmp_path / "agy.py", "agy", tmp_path / "argv.jsonl", tmp_path / "count.txt")
    cfg_a, _home_a = _config(
        tmp_path, items, {"agy": binary}, holder="holder-a", host="host-a",
        home=tmp_path / "a", ledger=ledger, lease_ttl_s=30,
    )
    cfg_b, _home_b = _config(
        tmp_path, items, {"agy": binary}, holder="holder-b", host="host-b",
        home=tmp_path / "b", ledger=ledger, lease_ttl_s=3600,
    )
    with pytest.raises(RuntimeError):
        _run(cfg_a, GitHub(), hooks={"after_claim": lambda: (_ for _ in ()).throw(RuntimeError("a"))})
    assert _run(cfg_b, GitHub()) == 0
    claims = [event for event in _events(ledger) if event["type"] == "CLAIM"]
    assert [event["holder"] for event in claims] == ["holder-a"]
    later = NOW + timedelta(seconds=31)
    assert _run(cfg_b, GitHub(), now=lambda: later) == 0
    claims = [event for event in _events(ledger) if event["type"] == "CLAIM"]
    assert [event["holder"] for event in claims] == ["holder-a", "holder-b"]
    releases = [event for event in _events(ledger) if event["type"] == "RELEASE"]
    assert len(releases) == 1 and releases[0]["holder"] == "holder-b"


def test_short_lease_is_renewed_once(tmp_path):
    env = _layout(tmp_path, mode="agy", lease_ttl_s=10, timeout_s=30)
    assert _run(env["cfg"], GitHub()) == 0
    kinds = [event["type"] for event in _events(env["ledger"])]
    assert kinds == ["CLAIM", "RENEW", "RELEASE"]


def test_provider_strikes_and_host_block(tmp_path):
    root = tmp_path / "strikes"
    items = root / "items"
    _write_items(items, [_item(name, [f"docs/{name}.md"]) for name in ("A", "B", "C", "D")])
    agy_count = root / "agy.txt"
    muse_count = root / "muse.txt"
    agy = _fake(root / "agy.py", "crash", root / "agy-argv.jsonl", agy_count)
    muse = _fake(root / "muse.py", "muse", root / "muse-argv.jsonl", muse_count)
    cfg, home = _config(
        root, items, {"agy": agy, "muse": muse}, providers=["agy", "muse"], ledger=root / "queue.jsonl",
    )
    assert _run(cfg, GitHub(), "--forever", until_idle=True) == 0
    assert _count(agy_count) == 3
    assert _count(muse_count) == 4
    state = json.loads((home / "host_loop_state.json").read_text(encoding="utf-8"))
    assert "agy" in state["unavailable"]
    assert state["host_status"] == "READY"
    assert all(event["result"].startswith("ACCEPTED ") for event in _events(root / "queue.jsonl") if event["type"] == "RELEASE")

    blocked = tmp_path / "blocked"
    _write_items(blocked / "items", [_item(name, [f"docs/{name}.md"]) for name in ("A", "B", "C", "D")])
    count = blocked / "count.txt"
    binary = _fake(blocked / "muse.py", "crash", blocked / "argv.jsonl", count)
    cfg, home = _config(
        blocked, blocked / "items", {"muse": binary}, providers=["muse"], ledger=blocked / "queue.jsonl",
    )
    assert _run(cfg, GitHub(), "--forever", until_idle=True) == 2
    assert _count(count) == 3
    claimed = [event["item_id"] for event in _events(blocked / "queue.jsonl") if event["type"] == "CLAIM"]
    assert claimed == ["A", "B", "C"]
    state = json.loads((home / "host_loop_state.json").read_text(encoding="utf-8"))
    assert state["host_status"] == "BLOCKED"
    assert _run(cfg, GitHub(), "--forever", until_idle=True) == 2
    assert _count(count) == 3
    ready = [item["id"] for item in WorkQueue(blocked / "items", blocked / "queue.jsonl").list_ready(now=NOW)]
    assert ready == ["D"]


def test_cursor_agent_and_path_decoy_do_not_launch(tmp_path):
    items = tmp_path / "items"
    _write_items(items, [_item("A", ["docs/a.md"])])
    cursor_count = tmp_path / "cursor.txt"
    muse_count = tmp_path / "muse.txt"
    cursor = _fake(tmp_path / "cursor.py", "agy", tmp_path / "c-argv.jsonl", cursor_count)
    muse = _fake(tmp_path / "muse.py", "muse", tmp_path / "m-argv.jsonl", muse_count)
    cfg, home = _config(
        tmp_path, items, {"cursor-agent": cursor, "muse": muse},
        providers=["cursor-agent", "muse"], ledger=tmp_path / "queue.jsonl",
    )
    assert _run(cfg, GitHub()) == 0
    assert _count(cursor_count) == 0 and _count(muse_count) == 1
    state = json.loads((home / "host_loop_state.json").read_text(encoding="utf-8"))
    assert "cursor-agent" in state["unavailable"]

    decoy_dir = tmp_path / "decoy-bin"
    decoy_dir.mkdir()
    decoy_count = tmp_path / "decoy.txt"
    _fake(decoy_dir / "agy", "agy", tmp_path / "decoy-argv.jsonl", decoy_count)
    lone = tmp_path / "lone"
    _write_items(lone / "items", [_item("A", ["docs/a.md"])])
    cfg, _home = _config(
        lone, lone / "items", {"agy": "agy"}, providers=["agy"], ledger=lone / "queue.jsonl",
    )
    old = os.environ.get("PATH")
    os.environ["PATH"] = str(decoy_dir)
    try:
        assert _run(cfg, GitHub()) == 0
    finally:
        if old is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = old
    assert _count(decoy_count) == 0
    assert "blocker=NO_PROVIDER" in _events(lone / "queue.jsonl")[-1]["result"]


def test_bad_prompt_is_skipped_without_a_claim(tmp_path, monkeypatch):
    env = _layout(tmp_path)
    monkeypatch.setattr(host_loop, "render_prompt", lambda item, holder: "-nope")
    assert _run(env["cfg"], GitHub()) == 0
    assert _events(env["ledger"]) == []
    state = json.loads((env["home"] / "host_loop_state.json").read_text(encoding="utf-8"))
    assert state["skipped"] == ["A"]
    assert _run(env["cfg"], GitHub()) == 0
    assert _events(env["ledger"]) == []


@pytest.mark.parametrize("boundary", ["before_claim", "after_claim", "after_provider_exit", "after_receipt"])
def test_restart_matrix(tmp_path, boundary):
    env = _layout(tmp_path, mode="agy")
    calls = []

    def runner(argv, workdir):
        calls.append(list(argv))
        return 0

    with pytest.raises(RuntimeError, match=boundary):
        _run(env["cfg"], GitHub(), hooks={boundary: lambda: (_ for _ in ()).throw(RuntimeError(boundary))}, tests_runner=runner)
    events = _events(env["ledger"])
    claims = [event for event in events if event["type"] == "CLAIM"]
    releases = [event for event in events if event["type"] == "RELEASE"]
    if boundary == "before_claim":
        assert claims == [] and releases == [] and _count(env["count"]) == 0 and calls == []
    elif boundary == "after_claim":
        assert len(claims) == 1 and releases == [] and _count(env["count"]) == 0 and calls == []
    elif boundary == "after_provider_exit":
        assert len(claims) == 1 and releases == [] and _count(env["count"]) == 1 and calls == []
    else:
        assert len(claims) == 1 and len(releases) == 1 and _count(env["count"]) == 1 and len(calls) == 1
    assert _run(env["cfg"], GitHub(), tests_runner=runner) == 0
    events = _events(env["ledger"])
    assert [event["type"] for event in events if event["type"] != "RENEW"] == ["CLAIM", "RELEASE"]
    assert sum(event["type"] == "CLAIM" for event in events) == 1
    assert sum(event["type"] == "RELEASE" for event in events) == 1
    assert sum(event["type"] == "RENEW" for event in events) == 0
    assert _count(env["count"]) == 1
    assert len(calls) == 1
    state = json.loads((env["home"] / "host_loop_state.json").read_text(encoding="utf-8"))
    assert state["in_flight"] is None
    log = (env["home"] / "run" / "host_loop_receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1


def test_cli_rejects_a_bad_invocation(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.host_loop"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == host_loop.EXIT_CONFIG
    env = _layout(tmp_path)
    assert host_loop.main(["--once", "--forever", "--host-config", str(env["cfg"])]) == host_loop.EXIT_CONFIG
    raw = json.loads(env["cfg"].read_text(encoding="utf-8"))
    raw["holder"] = "bad holder"
    env["cfg"].write_text(json.dumps(raw), encoding="utf-8")
    assert _run(env["cfg"], GitHub()) == host_loop.EXIT_CONFIG

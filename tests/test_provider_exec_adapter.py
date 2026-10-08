"""Headless provider_exec adapter. Imports the module directly.

courier_worker/adapter_bridge.py and courier_worker/adapter_runner.py are owned
by open PR #141, and courier_worker/service.py is owned by other open PRs, so
these tests do not register the adapter on the worker allowlist.
"""

import hashlib
import json
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import psutil
import pytest

from courier_worker.adapters import provider_exec

PROMPT = "summarize the unit without touching the network"
MARKER = provider_exec.TRUNCATION_MARKER


@pytest.fixture(autouse=True)
def _admit_heavy(monkeypatch):
    """Do not read host load. Admission is stubbed unless a test overrides it."""
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)


def _write_fake(directory: Path) -> str:
    script = directory / "fake_muse.py"
    script.write_text(_FAKE_SOURCE, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
    return str(script)


_FAKE_SOURCE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys, time
    from pathlib import Path

    forbidden = ("--yolo", "--disable-sandbox")
    if any(arg in forbidden for arg in sys.argv[1:]):
        sys.exit(97)
    if sys.argv[1:3] != ["exec", "--prompt-file"]:
        sys.stderr.write("bad argv\n")
        sys.exit(2)
    log = os.environ.get("FAKE_ARGV")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(sys.argv[1:]) + "\n")
    mode = os.environ.get("FAKE_MODE", "success")
    if mode == "fail":
        sys.stdout.write("provider-fail\n")
        sys.exit(3)
    if mode == "big":
        sys.stdout.buffer.write(b"Y" * 8000)
        sys.exit(0)
    if mode == "timeout":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        Path(os.environ["FAKE_PIDS"]).write_text(f"{os.getpid()}\n{child.pid}\n", encoding="utf-8")
        time.sleep(120)
        sys.exit(0)
    sys.stdout.write("provider-ok\n")
    sys.exit(0)
''').lstrip()


def _alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _config(binary: str, **extra) -> dict:
    config = {"binaries": {"muse": binary}}
    config.update(extra)
    return config


def _params(**extra) -> dict:
    params = {"provider": "muse", "prompt": PROMPT}
    params.update(extra)
    return params


def _run(tmp_path, monkeypatch, *, mode="success", params=None, config_extra=None, binary=None):
    fake = binary or _write_fake(tmp_path)
    argv_log = tmp_path / "argv.jsonl"
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setenv("FAKE_ARGV", str(argv_log))
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    workdir = tmp_path / f"work-{mode}"
    workdir.mkdir()
    extra = dict(config_extra or {})
    result = provider_exec.run(_params(**(params or {})), workdir, config=_config(fake, **extra))
    return result, workdir, argv_log


def _assert_no_private_path(result, tmp_path):
    public = json.dumps({
        "outcome": result.outcome,
        "reason_code": result.reason_code,
        "exit_code": result.exit_code,
        "output_sha256": result.output_sha256,
        "launched": result.launched,
        "parked": result.parked,
        "blocked": result.blocked,
        "truncated": result.truncated,
        "verified": result.verified,
    })
    assert str(tmp_path) not in public
    assert "Traceback" not in public


def test_a_success_returns_verified_output_hash(tmp_path, monkeypatch):
    result, workdir, argv_log = _run(tmp_path, monkeypatch)
    assert result.outcome == "success"
    assert result.launched is True
    assert result.exit_code == 0
    assert result.output == b"provider-ok\n"
    assert result.output_sha256 == hashlib.sha256(result.output).hexdigest()
    assert result.verified is True
    assert argv_log.is_file()
    recorded = json.loads(argv_log.read_text(encoding="utf-8").splitlines()[0])
    assert recorded[:2] == ["exec", "--prompt-file"]
    assert "--yolo" not in recorded and "--disable-sandbox" not in recorded
    prompt_path = Path(recorded[2])
    assert prompt_path.is_file()
    assert workdir in prompt_path.parents
    assert prompt_path.read_text(encoding="utf-8") == PROMPT
    _assert_no_private_path(result, tmp_path)


def test_b_nonzero_exit_is_failed(tmp_path, monkeypatch):
    result, _workdir, argv_log = _run(tmp_path, monkeypatch, mode="fail")
    assert result.outcome == "FAILED"
    assert result.reason_code == "NONZERO_EXIT"
    assert result.exit_code == 3
    assert result.verified is False
    assert result.launched is True
    assert argv_log.is_file()
    _assert_no_private_path(result, tmp_path)


def test_c_timeout_kills_only_own_child(tmp_path, monkeypatch):
    pid_file = tmp_path / "pids.txt"
    monkeypatch.setenv("FAKE_PIDS", str(pid_file))
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        result, _workdir, _argv_log = _run(
            tmp_path, monkeypatch, mode="timeout", params={"timeout_s": 8},
        )
        assert result.outcome == "FAILED"
        assert result.reason_code == "TIMEOUT"
        assert result.verified is False
        assert result.launched is True
        assert pid_file.is_file()
        root_pid, child_pid = (int(line) for line in pid_file.read_text(encoding="utf-8").splitlines())
        deadline = time_monotonic_deadline(5)
        while time_remaining(deadline) and (_alive(root_pid) or _alive(child_pid)):
            import time
            time.sleep(0.05)
        assert not _alive(root_pid)
        assert not _alive(child_pid)
        assert _alive(sentinel.pid)
        _assert_no_private_path(result, tmp_path)
    finally:
        if sentinel.poll() is None:
            sentinel.kill()
            sentinel.wait(timeout=5)


def time_monotonic_deadline(seconds):
    import time
    return time.monotonic() + seconds


def time_remaining(deadline):
    import time
    return time.monotonic() < deadline


def test_d_missing_binary_is_unavailable(tmp_path, monkeypatch):
    missing = tmp_path / "no-such-muse"
    argv_log = tmp_path / "argv.jsonl"
    monkeypatch.setenv("FAKE_ARGV", str(argv_log))
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    result = provider_exec.run(_params(), workdir, config=_config(str(missing)))
    assert result.outcome == "UNAVAILABLE"
    assert result.blocked is True
    assert result.reason_code == "BINARY_MISSING"
    assert result.launched is False
    assert result.verified is False
    assert result.output_sha256 is None
    assert result.exit_code is None
    assert not argv_log.exists()
    assert list(workdir.glob("prompt-*")) == []
    _assert_no_private_path(result, tmp_path)


def test_e_forbidden_flags_are_rejected(tmp_path, monkeypatch):
    for extra in ({"args": ["--yolo"]}, {"flags": ["--disable-sandbox"]}, {"yolo": True}, {"disable_sandbox": True}):
        result, _workdir, argv_log = _run(tmp_path, monkeypatch, params=extra)
        assert result.outcome == "rejected"
        assert result.reason_code == "FORBIDDEN_FLAG"
        assert result.launched is False
        assert result.verified is False
        assert not argv_log.exists()
        with pytest.raises(provider_exec.ProviderExecError) as raised:
            provider_exec.validate(_params(**extra))
        assert raised.value.reason_code == "FORBIDDEN_FLAG"
        _assert_no_private_path(result, tmp_path)


def test_f_admission_denied_does_not_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: False)
    result, workdir, argv_log = _run(tmp_path, monkeypatch)
    assert result.outcome == "deferred"
    assert result.parked is True
    assert result.reason_code == "ADMISSION_DENIED"
    assert result.launched is False
    assert result.verified is False
    assert not argv_log.exists()
    assert list(workdir.glob("prompt-*")) == []
    _assert_no_private_path(result, tmp_path)


def test_g_output_over_cap_is_truncated(tmp_path, monkeypatch):
    cap = 32
    result, _workdir, _argv_log = _run(
        tmp_path, monkeypatch, mode="big", config_extra={"max_output_bytes": cap},
    )
    assert result.outcome == "success"
    assert result.exit_code == 0
    assert result.truncated is True
    assert result.output.endswith(MARKER)
    assert result.output[:cap] == b"Y" * cap
    assert len(result.output) == cap + len(MARKER)
    assert result.output_sha256 == hashlib.sha256(result.output).hexdigest()
    assert result.verified is True
    _assert_no_private_path(result, tmp_path)


def test_h_two_sequential_tasks_both_execute(tmp_path, monkeypatch):
    fake = _write_fake(tmp_path)
    argv_log = tmp_path / "argv.jsonl"
    monkeypatch.setenv("FAKE_MODE", "success")
    monkeypatch.setenv("FAKE_ARGV", str(argv_log))
    monkeypatch.delenv("COURIER_PROVIDER_MUSE_BIN", raising=False)
    results = []
    for name in ("one", "two"):
        workdir = tmp_path / name
        workdir.mkdir()
        results.append(provider_exec.run(
            _params(prompt=f"unit {name}"), workdir, config=_config(fake),
        ))
    assert [item.outcome for item in results] == ["success", "success"]
    assert all(item.verified and item.launched for item in results)
    lines = argv_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    prompts = []
    for line in lines:
        recorded = json.loads(line)
        assert recorded[:2] == ["exec", "--prompt-file"]
        prompts.append(Path(recorded[2]).read_text(encoding="utf-8"))
    assert prompts == ["unit one", "unit two"]

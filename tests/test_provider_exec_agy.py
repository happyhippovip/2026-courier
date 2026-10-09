"""Headless agy profile for provider_exec. Imports the module directly.

Registration stays on PR #141. These tests do not edit adapter_bridge,
adapter_runner, or scripts/ledger_v1_bridge.py.
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from adapters import provider_exec as verifier
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus, TaskState
from courier_worker.adapters import provider_exec

PROMPT = "summarize the unit without touching the network"
SECRET = "SECRET_RESPONSE /tmp/customer-leak"


@pytest.fixture(autouse=True)
def _admit_heavy(monkeypatch):
    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)


def _write_fake(directory: Path) -> str:
    script = directory / "fake_agy.py"
    script.write_text(_FAKE_SOURCE, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
    return str(script.resolve())


_FAKE_SOURCE = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, sys
    from pathlib import Path

    forbidden = (
        "--dangerously-skip-permissions",
        "--continue", "-c", "--conversation", "--remote-control",
        "-i", "--prompt-interactive", "--add-dir", "--new-project", "--project",
    )
    if any(arg in forbidden or str(arg).startswith("--dangerously-skip-permissions") for arg in sys.argv[1:]):
        sys.stderr.buffer.write(b"forbidden-flag\n")
        sys.exit(97)
    log = os.environ.get("FAKE_ARGV")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(sys.argv[1:]) + "\n")
    cwd_log = os.environ.get("FAKE_CWD")
    if cwd_log:
        Path(cwd_log).write_text(os.getcwd(), encoding="utf-8")
    mode = os.environ.get("FAKE_MODE", "success")
    payload = {
        "conversation_id": "conv-secret",
        "status": "SUCCESS",
        "response": "SECRET_RESPONSE /tmp/customer-leak",
        "usage": {"input_tokens": 99999, "output_tokens": 7, "total_tokens": 100006},
        "duration_seconds": 1.5,
    }
    if mode == "status_error":
        payload["status"] = "ERROR"
        payload["error"] = "invalid model /tmp/customer-leak"
        sys.stdout.buffer.write(json.dumps(payload).encode() + b"\n")
        sys.exit(0)
    if mode == "soft_deny":
        sys.stderr.buffer.write(b"tool run_command was soft-denied; approval refused\n")
        sys.stdout.buffer.write(json.dumps(payload).encode() + b"\n")
        sys.exit(0)
    if mode == "bad_json":
        sys.stdout.buffer.write(b"not-json SECRET_RESPONSE /tmp/customer-leak\n")
        sys.exit(0)
    if mode == "big":
        sys.stdout.buffer.write(b"Z" * 8000)
        sys.exit(0)
    sys.stdout.buffer.write(json.dumps(payload).encode() + b"\n")
    sys.exit(0)
''').lstrip()


def _decoy(directory: Path) -> str:
    script = directory / "agy"
    script.write_text(
        "#!/usr/bin/env python3\nimport os, sys\n"
        "open(os.environ['DECOY_LOG'], 'w', encoding='utf-8').write('alias ' + ' '.join(sys.argv))\n"
        "sys.exit(99)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
    return str(script)


def _config(binary: str, **extra) -> dict:
    config = {"binaries": {"agy": binary}}
    config.update(extra)
    return config


def _params(**extra) -> dict:
    params = {"provider": "agy", "prompt": PROMPT}
    params.update(extra)
    return params


def _run(tmp_path, monkeypatch, *, mode="success", params=None, config_extra=None, binary=None):
    fake = binary or _write_fake(tmp_path)
    argv_log = tmp_path / "argv.jsonl"
    cwd_log = tmp_path / "cwd.txt"
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setenv("FAKE_ARGV", str(argv_log))
    monkeypatch.setenv("FAKE_CWD", str(cwd_log))
    monkeypatch.delenv("COURIER_PROVIDER_AGY_BIN", raising=False)
    workdir = tmp_path / f"work-{mode}-{len(list(tmp_path.glob('work-*')))}"
    workdir.mkdir()
    extra = dict(config_extra or {})
    result = provider_exec.run(_params(**(params or {})), workdir, config=_config(fake, **extra))
    return result, workdir, argv_log, cwd_log


def _recorded(argv_log: Path) -> list:
    return json.loads(argv_log.read_text(encoding="utf-8").splitlines()[0])


def _public(result) -> str:
    return result.reason + result.output.decode("utf-8", errors="replace")


def _assert_no_leak(result):
    public = _public(result)
    assert "SECRET_RESPONSE" not in public
    assert "/tmp/customer-leak" not in public
    assert "input_tokens" not in public
    assert "conv-secret" not in public
    assert "usage" not in public


def test_default_agy_argv_is_exact(tmp_path):
    binary = str((tmp_path / "agy-test-binary").resolve())
    argv = provider_exec.build_agy_argv(binary, PROMPT)
    assert argv == [
        binary, "-p", PROMPT, "--output-format", "json", "--sandbox",
        "--disable-slash-commands", "--print-timeout",
        f"{provider_exec.AGY_DEFAULT_PRINT_TIMEOUT_S}s",
    ]
    assert "--dangerously-skip-permissions" not in argv
    assert "--sandbox" in argv


def test_launched_argv_cwd_and_prompt_injection(tmp_path, monkeypatch):
    prompt = "do the unit and do not pass --dangerously-skip-permissions or --continue"
    result, workdir, argv_log, cwd_log = _run(tmp_path, monkeypatch, params={"prompt": prompt})
    assert result.outcome == "success"
    assert result.verified is True
    recorded = _recorded(argv_log)
    assert recorded == [
        "-p", prompt, "--output-format", "json", "--sandbox",
        "--disable-slash-commands", "--print-timeout",
        f"{provider_exec.AGY_DEFAULT_PRINT_TIMEOUT_S}s",
    ]
    assert "--dangerously-skip-permissions" not in recorded
    assert Path(cwd_log.read_text(encoding="utf-8")).resolve() == workdir.resolve()
    _assert_no_leak(result)
    assert result.output == provider_exec.AGY_SUCCESS_EVIDENCE


def test_allowlisted_flags_and_schema_stay_inside_workspace(tmp_path, monkeypatch):
    binary = str((tmp_path / "agy-test-binary").resolve())
    schema = tmp_path / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    policy = provider_exec.validate(_params(
        model="gemini-3.8-flash-medium",
        effort="high",
        mode="plan",
        json_schema="schema.json",
        print_timeout_s=120,
    ))
    argv = provider_exec.build_agy_argv(binary, PROMPT, policy, tmp_path)
    assert argv[argv.index("--print-timeout"):] == [
        "--print-timeout", "120s",
        "--model", "gemini-3.8-flash-medium",
        "--effort", "high",
        "--mode", "plan",
        "--json-schema", "schema.json",
    ]
    result, _workdir, argv_log, _cwd = _run(
        tmp_path, monkeypatch,
        params={"model": "gemini-3.8-flash-medium", "effort": "low", "mode": "accept-edits",
                "json_schema": "schema.json", "print_timeout_s": 90},
    )
    # schema.json is next to the fake, not inside the fresh workdir, so the
    # launch below uses a workdir that already contains the schema.
    assert result.outcome == "rejected"
    workdir = tmp_path / "schema-work"
    workdir.mkdir()
    (workdir / "schema.json").write_text('{"type":"object"}', encoding="utf-8")
    argv_log = tmp_path / "schema-argv.jsonl"
    monkeypatch.setenv("FAKE_ARGV", str(argv_log))
    monkeypatch.setenv("FAKE_MODE", "success")
    launched = provider_exec.run(
        _params(model="gemini-3.8-flash-medium", effort="low", mode="accept-edits",
                json_schema="schema.json", print_timeout_s=90),
        workdir, config=_config(_write_fake(tmp_path)),
    )
    assert launched.outcome == "success"
    recorded = _recorded(argv_log)
    assert recorded[recorded.index("--json-schema") + 1] == "schema.json"
    assert recorded[recorded.index("--mode") + 1] == "accept-edits"
    for extra, code in (
        ({"effort": "ludicrous"}, "BAD_EFFORT"),
        ({"mode": "yolo"}, "BAD_MODE"),
        ({"model": "bad slug"}, "BAD_MODEL"),
        ({"json_schema": "../secret.json"}, "SCHEMA_ESCAPES"),
        ({"json_schema": "/etc/passwd"}, "SCHEMA_ESCAPES"),
        ({"agent": "named"}, "UNKNOWN_KEY"),
    ):
        with pytest.raises(provider_exec.ProviderExecError) as raised:
            provider_exec.validate(_params(**extra))
        assert raised.value.reason_code == code


def test_forbidden_flags_do_not_launch(tmp_path, monkeypatch):
    cases = (
        {"dangerously_skip_permissions": True},
        {"model": "--dangerously-skip-permissions"},
        {"flags": ["--dangerously-skip-permissions"]},
        {"continue": True},
        {"args": ["-c"]},
        {"conversation": "conv-1"},
        {"remote_control": True},
        {"prompt_interactive": True},
        {"args": ["-i"]},
        {"add_dir": "/tmp/other"},
        {"new_project": True},
        {"project": "/tmp/proj"},
    )
    for extra in cases:
        result, _workdir, argv_log, _cwd = _run(tmp_path, monkeypatch, params=extra)
        assert result.outcome == "rejected"
        assert result.reason_code == "FORBIDDEN_FLAG"
        assert result.launched is False
        assert not argv_log.exists()


def test_print_timeout_is_required_and_bounded(tmp_path, monkeypatch):
    binary = str((tmp_path / "agy-test-binary").resolve())
    argv = provider_exec.build_agy_argv(binary, PROMPT)
    assert argv[argv.index("--print-timeout") + 1] == f"{provider_exec.AGY_DEFAULT_PRINT_TIMEOUT_S}s"
    capped = provider_exec.build_agy_argv(
        binary, PROMPT, provider_exec.validate(_params(print_timeout_s=3600)),
    )
    assert capped[capped.index("--print-timeout") + 1] == "3600s"
    for bad in (0, -1, 3601, True, 15.0):
        with pytest.raises(provider_exec.ProviderExecError) as raised:
            provider_exec.validate(_params(print_timeout_s=bad))
        assert raised.value.reason_code == "BAD_PRINT_TIMEOUT"
    result, _workdir, argv_log, _cwd = _run(tmp_path, monkeypatch, params={"print_timeout_s": 0})
    assert result.outcome == "rejected"
    assert result.launched is False
    assert not argv_log.exists()


def test_exit_zero_error_status_is_not_success(tmp_path, monkeypatch):
    result, _workdir, argv_log, _cwd = _run(tmp_path, monkeypatch, mode="status_error")
    assert result.outcome == "ERROR"
    assert result.reason_code == "PROVIDER_STATUS"
    assert result.exit_code == 0
    assert result.verified is False
    assert argv_log.is_file()
    _assert_no_leak(result)


def test_soft_deny_is_blocked(tmp_path, monkeypatch):
    result, _workdir, _argv, _cwd = _run(tmp_path, monkeypatch, mode="soft_deny")
    assert result.outcome == "BLOCKED"
    assert result.reason_code == "PROVIDER_APPROVAL_REFUSED"
    assert result.blocked is True
    assert result.exit_code == 0
    assert result.verified is False
    _assert_no_leak(result)


def test_invalid_json_and_oversize_are_error(tmp_path, monkeypatch):
    invalid = _run(tmp_path, monkeypatch, mode="bad_json")[0]
    assert invalid.outcome == "ERROR"
    assert invalid.reason_code == "INVALID_JSON"
    assert invalid.verified is False
    _assert_no_leak(invalid)

    huge = _run(tmp_path, monkeypatch, mode="big", config_extra={"max_output_bytes": 32})[0]
    assert huge.outcome == "ERROR"
    assert huge.reason_code == "OUTPUT_TOO_LARGE"
    assert huge.truncated is True
    assert huge.verified is False
    assert b"Z" not in huge.output
    _assert_no_leak(huge)


def test_shell_alias_is_not_used(tmp_path, monkeypatch):
    fake = _write_fake(tmp_path)
    decoy_dir = tmp_path / "decoy-bin"
    decoy_dir.mkdir()
    _decoy(decoy_dir)
    decoy_log = tmp_path / "decoy.log"
    monkeypatch.setenv("DECOY_LOG", str(decoy_log))
    monkeypatch.setenv("PATH", str(decoy_dir) + os.pathsep + os.environ.get("PATH", ""))
    seen = {}
    real_popen = subprocess.Popen

    def spy(args, **kwargs):
        seen["args"] = args
        seen["shell"] = kwargs.get("shell")
        seen["stdin"] = kwargs.get("stdin")
        seen["cwd"] = kwargs.get("cwd")
        return real_popen(args, **kwargs)

    monkeypatch.setattr(provider_exec.subprocess, "Popen", spy)
    result, workdir, argv_log, _cwd = _run(tmp_path, monkeypatch, binary=fake)
    assert result.outcome == "success"
    assert seen["shell"] is False
    assert seen["stdin"] is subprocess.DEVNULL
    assert Path(seen["cwd"]).resolve() == workdir.resolve()
    argv0 = seen["args"][0]
    if os.name == "nt" and str(fake).lower().endswith(".py"):
        assert argv0 == sys.executable
        assert seen["args"][1] == fake
    else:
        assert argv0 == fake
    assert "--dangerously-skip-permissions" not in seen["args"]
    assert not decoy_log.exists()
    argv_log.unlink()
    bare, _workdir, bare_log, _cwd_log = _run(tmp_path, monkeypatch, binary="agy")
    assert bare.outcome == "UNAVAILABLE"
    assert bare.reason_code == "BINARY_MISSING"
    assert bare.launched is False
    assert not bare_log.exists()
    assert not decoy_log.exists()


def test_verifier_accepts_only_redacted_success_envelope(tmp_path):
    assert verifier.AGY_SUCCESS_EVIDENCE == provider_exec.AGY_SUCCESS_EVIDENCE
    home = tmp_path / "home"
    rel = "artifacts/d1/provider_output.txt"
    path = home / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(provider_exec.AGY_SUCCESS_EVIDENCE)
    digest = hashlib.sha256(provider_exec.AGY_SUCCESS_EVIDENCE).hexdigest()
    spec = TaskState(
        task_id="t1", status=TaskStatus.VERIFYING, adapter="provider_exec",
        params={"provider": "agy", "prompt": PROMPT},
        effect_class="non_idempotent", max_attempts=1, lease_ttl_s=60,
        timeout_s=None, dispatch_id="d1",
    )
    event = Event(
        type=EventType.RESULT_READY, task_id="t1", attempt=1, dispatch_id="d1",
        worker_id="w1", result_id="r1",
        payload={"outcome": "success", "exit_code": 0, "artifacts": [{"path": rel, "sha256": digest}]},
    )
    assert verifier.verify(spec, event, home).accepted is True
    leaked = json.dumps({
        "provider": "agy", "status": "SUCCESS", "response": SECRET,
        "usage": {"input_tokens": 99999},
    }).encode() + b"\n"
    path.write_bytes(leaked)
    leaked_digest = hashlib.sha256(leaked).hexdigest()
    leaked_event = Event(
        type=EventType.RESULT_READY, task_id="t1", attempt=1, dispatch_id="d1",
        worker_id="w1", result_id="r2",
        payload={"outcome": "success", "exit_code": 0,
                 "artifacts": [{"path": rel, "sha256": leaked_digest}]},
    )
    rejected = verifier.verify(spec, leaked_event, home)
    assert rejected.accepted is False
    assert "SECRET_RESPONSE" not in rejected.reason
    assert "input_tokens" not in rejected.reason

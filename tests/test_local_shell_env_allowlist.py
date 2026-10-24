"""H12: a local_shell child gets an allowlisted environment, never the worker's credentials.

The worker host may hold provider keys (it also runs provider_exec). A local_shell
command is arbitrary argv; inheriting those keys lets it reach a paid provider outside
CostGate and copies credentials into a process that writes evidence files.
"""
import json
import os
import sys

import pytest

from adapters import local_shell
from adapters.local_shell import LocalShellError

DUMP = [sys.executable, "-c", "import json, os; open('out.txt', 'w').write(json.dumps(dict(os.environ)))"]
CREDENTIALS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GITHUB_TOKEN",
               "GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "COURIER_CONTROLLER_TOKEN",
               "XAI_API_KEY", "MY_SERVICE_PASSWORD", "SESSION_COOKIE"]


def _child_env(tmp_path, params_env=None):
    params = {"command": DUMP, "write": "out.txt"}
    if params_env is not None:
        params["env"] = params_env
    assert local_shell.run(params, tmp_path).outcome == "success"
    return json.loads((tmp_path / "out.txt").read_text())


@pytest.mark.parametrize("name", CREDENTIALS)
def test_worker_credentials_do_not_reach_the_child(tmp_path, monkeypatch, name):
    monkeypatch.setenv(name, "sentinel-not-a-real-value")
    assert name not in _child_env(tmp_path)


def test_unlisted_worker_variables_do_not_reach_the_child(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_SOME_INTERNAL_SETTING", "x")
    assert "COURIER_SOME_INTERNAL_SETTING" not in _child_env(tmp_path)


def test_the_child_still_gets_path_and_the_task_env(tmp_path):
    env = _child_env(tmp_path, {"LOCAL_FLAG": "on"})
    assert env.get("PATH") and env["LOCAL_FLAG"] == "on"


@pytest.mark.parametrize("name", ["OPENAI_API_KEY", "github_token", "Db_Password", "X_SECRET", "AUTH_COOKIE",
                                  "AWS_ACCESS_KEY_ID", "SOME_CREDENTIALS"])
def test_a_task_cannot_carry_a_credential_in_its_env(tmp_path, name):
    # task params are journaled; a credential there would be persisted and shown.
    with pytest.raises(LocalShellError, match="credential"):
        local_shell.run({"command": DUMP, "env": {name: "v"}}, tmp_path)
    with pytest.raises(LocalShellError, match="credential"):
        local_shell._params({"command": DUMP, "env": {name: "v"}})


@pytest.mark.parametrize("name", ["PATH", "PYTHONPATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONSTARTUP",
                                  "NODE_OPTIONS", "BASH_ENV"])
def test_a_task_cannot_override_loader_or_path_variables(tmp_path, name):
    with pytest.raises(LocalShellError, match="not allowed"):
        local_shell._params({"command": DUMP, "env": {name: "x"}})


# V8 red team: a self-declared 0.0 estimate must not start a provider CLI through local_shell.
PY = sys.executable


@pytest.mark.parametrize("argv", [
    ["codex", "exec", "hi"],
    ["/usr/local/bin/claude", "-p", "hi"],
    ["C:\\Tools\\gemini.cmd", "-p", "x"],
    ["agy.exe", "run"],
    ["/usr/bin/env", "claude", "-p", "hi"],
    ["env", "FOO=1", "-i", "codex", "exec"],
    ["npx", "@openai/codex", "exec"],
    ["npx", "-y", "@anthropic-ai/claude-code", "-p", "x"],
    ["timeout", "5", "grok", "ask"],
    ["sh", "-c", "agy -p hi"],
    ["bash", "-lc", "cd /tmp && claude -p hi"],
    ["cmd", "/c", "codex exec x"],
    ["powershell", "-NoProfile", "-Command", "gemini -p x"],
    [PY, "-c", "import subprocess; subprocess.run(['gemini', '-p', 'x'])"],
    ["node", "-e", "require('child_process').execSync('codex exec x')"],
    ["cursor-agent", "-p", "x"],
])
def test_a_provider_cli_is_refused_before_anything_starts(tmp_path, argv):
    with pytest.raises(LocalShellError, match="provider CLI"):
        local_shell._params({"command": argv, "estimated_cost_eur": 0.0})
    with pytest.raises(LocalShellError, match="provider CLI"):
        local_shell.run({"command": argv, "write": "out.txt"}, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("argv", [
    [PY, "-c", "open('out.txt', 'w').write('shell-made')"],
    [PY, "/repo/scripts/run_antigravity_bridge.py", "--job-file", "j.json"],
    ["grep", "-r", "claude", "docs"],
    ["git", "log", "--author", "codex-bot"],
    [PY, "-c", "print('geminid'); x = 'claudette'"],
])
def test_ordinary_commands_that_only_mention_a_provider_still_pass(argv):
    assert local_shell._params({"command": argv})["command"] == argv


def test_the_child_does_not_see_the_workers_home(tmp_path, monkeypatch):
    # CLI logins live in the home folder (~/.codex, ~/.claude, ~/.gemini, %APPDATA%).
    monkeypatch.setenv("HOME", "/home/worker-sentinel")
    monkeypatch.setenv("USERPROFILE", "C:\\Users\\worker-sentinel")
    env = _child_env(tmp_path)
    homes = {env.get(name) for name in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "APPDATA", "LOCALAPPDATA")}
    assert len(homes) == 1 and None not in homes
    home = homes.pop()
    assert "worker-sentinel" not in home
    assert str(tmp_path) not in home                          # not inside the workdir (no cache as evidence)
    assert not os.path.exists(home)                           # removed after the run
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.txt"]


def test_git_identity_and_proxy_without_password_pass_but_secrets_do_not(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:pw@proxy:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:8080")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")
    monkeypatch.setenv("CODEX_HOME", "/home/worker/.codex")
    env = _child_env(tmp_path, {"GIT_AUTHOR_NAME": "Courier", "GIT_AUTHOR_EMAIL": "c@example.com",
                                "KEYBOARD_LAYOUT": "de"})
    assert env["GIT_AUTHOR_NAME"] == "Courier" and env["KEYBOARD_LAYOUT"] == "de"
    assert env.get("HTTP_PROXY") == "http://proxy:8080" and "HTTPS_PROXY" not in env
    assert "SSH_AUTH_SOCK" not in env and "CODEX_HOME" not in env


@pytest.mark.parametrize("name", ["CODEX_HOME", "CLAUDE_CONFIG_DIR", "GIT_ASKPASS", "GIT_SSH_COMMAND",
                                  "GIT_CONFIG_GLOBAL", "DBUS_SESSION_BUS_ADDRESS", "NODE_PATH"])
def test_a_task_cannot_point_the_child_at_a_login(tmp_path, name):
    with pytest.raises(LocalShellError, match="login"):
        local_shell._params({"command": DUMP, "env": {name: "/x"}})


def test_a_task_cannot_carry_a_url_with_a_password(tmp_path):
    with pytest.raises(LocalShellError, match="credential"):
        local_shell._params({"command": DUMP, "env": {"DATABASE_URL": "postgres://a:b@db/x"}})


def test_a_read_only_file_in_the_temporary_home_is_still_removed(tmp_path):
    script = ("import os, stat; p = os.path.join(os.environ['HOME'], 'ro.txt'); open(p, 'w').write('x'); "
              "os.chmod(p, stat.S_IREAD); open('out.txt', 'w').write(os.environ['HOME'])")
    assert local_shell.run({"command": [sys.executable, "-c", script], "write": "out.txt"}, tmp_path).outcome == "success"
    assert not os.path.exists((tmp_path / "out.txt").read_text())


def test_no_temporary_home_is_a_local_shell_error(tmp_path, monkeypatch):
    import tempfile

    def broken(**kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(tempfile, "mkdtemp", broken)
    with pytest.raises(LocalShellError, match="temporary home"):
        local_shell.run({"command": DUMP, "write": "out.txt"}, tmp_path)

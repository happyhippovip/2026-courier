"""Regression guards for the safe Muse slot launcher.

Scope: scripts/windows_muse_wall/launch_safe_slot.ps1 ONLY.

The launcher relocates Muse data dirs for one child process: absolute
Workspace/DataHome, both pre-existing, XDG_DATA_HOME set for the child and
restored (or unset) in `finally`, auto-update/login pinned off for the child
and restored. It must never pass --yolo or sandbox-disable flags, run ACL
commands, use Invoke-Expression, or handle credentials.
"""
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

WALL_DIR = Path(__file__).resolve().parent.parent / "scripts" / "windows_muse_wall"
SCRIPT = WALL_DIR / "launch_safe_slot.ps1"

POWERSHELL = Path(
    os.environ.get("SystemRoot", r"C:\Windows")
) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def text():
    return SCRIPT.read_text(encoding="utf-8")


def code_lines():
    """Script lines minus block comments (<# ... #>) and full-line comments."""
    body = re.sub(r"<#.*?#>", "", text(), flags=re.DOTALL)
    lines = []
    for line in body.splitlines():
        if line.strip().startswith("#"):
            continue
        lines.append(line)
    return lines


def code():
    return "\n".join(code_lines())


def run_ps(command, env=None, timeout=60):
    # powershell.exe emits OEM-encoded (German) error text; decode leniently so
    # non-ASCII bytes never fail the capture. All assertions match ASCII tokens.
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )


# --- static shape -----------------------------------------------------------

def test_params_are_mandatory():
    body = code()
    assert "[Parameter(Mandatory=$true)][string]$Workspace" in body
    assert "[Parameter(Mandatory=$true)][string]$DataHome" in body


def test_requires_absolute_existing_directories():
    body = code()
    assert "IsPathRooted" in body
    assert "Test-Path -LiteralPath" in body
    assert "PathType Container" in body


def test_data_home_is_child_scoped_and_restored():
    body = code()
    assert "$env:XDG_DATA_HOME = (Get-Item -LiteralPath $DataHome).FullName" in body
    assert "finally" in body
    assert "Restore-SlotEnvValue 'XDG_DATA_HOME' $previousData" in body
    # A previously-unset variable must be unset again, never empty-stringed.
    assert "$null -eq $Previous" in body
    assert 'Remove-Item "Env:\\$Name"' in body


def test_auto_update_and_login_pinned_then_restored():
    body = code()
    assert "$env:MUSE_NO_AUTO_UPDATE = '1'" in body
    assert "$env:MUSE_LOGIN = '0'" in body
    assert "Restore-SlotEnvValue 'MUSE_NO_AUTO_UPDATE' $previousUpdate" in body
    assert "Restore-SlotEnvValue 'MUSE_LOGIN' $previousLogin" in body


def test_env_captured_before_throwing_lookup():
    body = code()
    assert body.index("$previousData = $env:XDG_DATA_HOME") < body.index(
        "Get-Command muse -ErrorAction Stop"
    )


def test_no_yolo_or_sandbox_disable():
    lowered = code().lower()
    assert "--yolo" not in lowered
    assert "disable-sandbox" not in lowered


def test_no_invoke_expression_in_code():
    hits = [
        line
        for line in code_lines()
        if re.match(r"\s*Invoke-Expression\b", line, re.IGNORECASE)
    ]
    assert hits == []


def test_no_acl_commands():
    lowered = code().lower()
    for token in ("set-acl", "get-acl", "icacls", "takeown", "cacls", "setaccessrule"):
        assert token not in lowered, token


def test_no_credential_handling():
    lowered = code().lower()
    for token in ("securestring", "pscredential", "get-credential", "clientsecret", "password"):
        assert token not in lowered, token


# --- functional: validation fails before any mutation -----------------------

def test_relative_workspace_rejected_before_env_mutation():
    with tempfile.TemporaryDirectory() as tmp:
        sentinel = "SENTINEL_%s" % uuid.uuid4().hex[:8].upper()
        cmd = (
            "$env:XDG_DATA_HOME = '%s'; "
            "try { & '%s' -Workspace 'relative\\path' -DataHome '%s' } "
            "catch { 'CAUGHT: ' + $_.Exception.Message }; "
            "'AFTER:' + $env:XDG_DATA_HOME"
            % (sentinel, SCRIPT, tmp)
        )
        result = run_ps(cmd)
    assert "CAUGHT:" in result.stdout, result.stdout + result.stderr
    assert "existing absolute directory" in result.stdout
    assert "AFTER:" + sentinel in result.stdout


def test_missing_muse_lookup_leaves_env_intact():
    with tempfile.TemporaryDirectory() as tmp:
        sentinel = "SENTINEL_%s" % uuid.uuid4().hex[:8].upper()
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        env = {
            "SystemRoot": system_root,
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
            "PATH": os.path.join(system_root, "System32"),
            "XDG_DATA_HOME": sentinel,
        }
        cmd = (
            "try { & '%s' -Workspace '%s' -DataHome '%s' } "
            "catch { 'CAUGHT: ' + $_.Exception.Message }; "
            "'AFTER:' + $env:XDG_DATA_HOME"
            % (SCRIPT, tmp, tmp)
        )
        result = run_ps(cmd, env=env)
    assert "CAUGHT:" in result.stdout, result.stdout + result.stderr
    assert "AFTER:" + sentinel in result.stdout


# --- functional: stub-muse launch proves child scope + restore + flags ------

STUB = (
    "@echo off\r\n"
    "echo CHILD_XDG=%XDG_DATA_HOME%\r\n"
    "echo CHILD_UPDATE=%MUSE_NO_AUTO_UPDATE%\r\n"
    "echo CHILD_LOGIN=%MUSE_LOGIN%\r\n"
    "echo CHILD_ARGS=%*\r\n"
    "exit /b 0\r\n"
)


def test_stub_launch_scopes_env_and_passes_no_disable_flags():
    with tempfile.TemporaryDirectory() as tmp:
        stub_dir = Path(tmp) / "bin"
        stub_dir.mkdir()
        (stub_dir / "muse.cmd").write_text(STUB, encoding="ascii")
        data_home = Path(tmp) / "data"
        data_home.mkdir()
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        env = {
            "SystemRoot": system_root,
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
            "TEMP": tmp,
            "TMP": tmp,
            "PATH": str(stub_dir)
            + os.pathsep
            + os.path.join(system_root, "System32"),
        }
        cmd = (
            "& '%s' -Workspace '%s' -DataHome '%s'; "
            "'EXIT:' + $LASTEXITCODE; "
            "'RESTORED_XDG:' + (Test-Path Env:\\XDG_DATA_HOME); "
            "'RESTORED_UPDATE:' + (Test-Path Env:\\MUSE_NO_AUTO_UPDATE); "
            "'RESTORED_LOGIN:' + (Test-Path Env:\\MUSE_LOGIN)"
            % (SCRIPT, tmp, data_home)
        )
        result = run_ps(cmd, env=env)
    out = result.stdout
    assert result.returncode == 0, out + result.stderr
    assert "CHILD_XDG=" + str(data_home) in out, out
    assert "CHILD_UPDATE=1" in out, out
    assert "CHILD_LOGIN=0" in out, out
    lowered = out.lower()
    assert "--yolo" not in lowered, out
    assert "disable-sandbox" not in lowered, out
    # Previously unset: unset again, not left as empty strings.
    assert "RESTORED_XDG:False" in out, out
    assert "RESTORED_UPDATE:False" in out, out
    assert "RESTORED_LOGIN:False" in out, out

"""Static regression guards for the opt-in safe-slot launcher.

SAFE_DATAHOME=UNPROVEN: no DataHome path is validated here and no runtime
proof is claimed. These tests pin the script's safe STRUCTURE only:

- existing absolute directories required (Workspace + DataHome)
- no --yolo, no sandbox-disable flag, --disable-approval present
- child-only environment (XDG_DATA_HOME / MUSE_NO_AUTO_UPDATE / MUSE_LOGIN)
  with parent restore in finally, captured BEFORE any throwing lookup
- no ACL changes, no credential copies, no Invoke-Expression,
  no arbitrary shell execution (exactly one call-operator invocation)

Runtime proof (real Muse slot, sandbox still enabled) requires a working
shell runner and is tracked separately.
"""
from pathlib import Path

LAUNCHER = (
    Path(__file__).resolve().parents[1]
    / "scripts/windows_muse_wall/launch_safe_slot.ps1"
)


def read():
    assert LAUNCHER.is_file()
    return LAUNCHER.read_text(encoding="utf-8")


def test_mandatory_workspace_and_datahome_params():
    text = read()
    assert "[Parameter(Mandatory=$true)][string]$Workspace" in text
    assert "[Parameter(Mandatory=$true)][string]$DataHome" in text


def test_existing_absolute_directories_required():
    text = read()
    assert "[IO.Path]::IsPathRooted" in text
    assert "Test-Path -LiteralPath" in text
    assert "PathType Container" in text
    assert "throw" in text


def test_no_yolo_and_no_sandbox_disable():
    text = read()
    assert "--yolo" not in text
    assert "--disable-sandbox" not in text.lower()
    assert "BypassSandbox" not in text


def test_disable_approval_present():
    assert "--disable-approval" in read()


def test_previous_environment_captured_before_throwing_lookup():
    text = read()
    capture = text.index("$previousData = $env:XDG_DATA_HOME")
    lookup = text.index("Get-Command muse")
    assert capture < lookup


def test_environment_restored_in_finally():
    text = read()
    finally_at = text.index("finally")
    for restore in (
        "$env:XDG_DATA_HOME = $previousData",
        "$env:MUSE_NO_AUTO_UPDATE = $previousUpdate",
        "$env:MUSE_LOGIN = $previousLogin",
    ):
        assert restore in text
        assert text.index(restore) > finally_at


def test_scoped_update_and_login_flags():
    text = read()
    assert "$env:MUSE_NO_AUTO_UPDATE = '1'" in text
    assert "$env:MUSE_LOGIN = '0'" in text


def test_no_acl_or_credential_cmdlets():
    lowered = read().lower()
    for banned in ("set-acl", "get-acl", "icacls", "takeown", "cacls", "copy-item"):
        assert banned not in lowered


def test_no_invoke_expression():
    assert "Invoke-Expression" not in read()


def test_single_fixed_muse_invocation():
    lines = [line.strip() for line in read().splitlines()]
    invoked = [line for line in lines if line.startswith("& ")]
    assert len(invoked) == 1
    assert invoked[0].startswith("& $museCommand")
    assert "cmd /c" not in read().lower()

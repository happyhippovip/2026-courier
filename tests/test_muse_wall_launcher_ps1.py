"""Regression guards for the Windows Terminal wall launcher root cause.

2026-09-24 defect (OBSERVED): muse_wall_launcher.ps1 built one command
STRING with quoted subcommands (`"new-tab"` / `"split-pane"`) chained by
`;` and executed it via Invoke-Expression. PowerShell split the string at
`;` (only the first wt call ever ran) and wt.exe received the literal
quoted word `"new-tab"`, which it does not recognise -- Windows Terminal
then opened its Help popup instead of the wall.

These tests pin the fixed shape: bare subcommand names, ";" passed as a
discrete wt separator argument, no Invoke-Expression, single-instance
attach (`-w 0`) preserved, and every wrapper pointed at the canonical
repo-root runtime (SECOND_TRUTH_STORE=NO).
"""
from pathlib import Path
import shutil
import subprocess

import pytest

WALL_DIR = Path(__file__).resolve().parent.parent / "scripts" / "windows_muse_wall"


def read(name):
    return (WALL_DIR / name).read_text(encoding="utf-8")


def test_launcher_has_no_quoted_subcommands():
    text = read("muse_wall_launcher.ps1")
    assert '`"new-tab"`' not in text
    assert '`"split-pane"`' not in text
    assert '"new-tab"' not in text
    assert '"split-pane"' not in text


def test_launcher_does_not_execute_invoke_expression():
    shell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell parser is required")
    script = r"""
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        (Join-Path $PWD 'muse_wall_launcher.ps1'), [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw ($errors | Out-String) }
    $ast.FindAll({param($node)
        $node -is [System.Management.Automation.Language.CommandAst] -and
        $node.GetCommandName() -in @('Invoke-Expression', 'iex')
    }, $true) | ForEach-Object { $_.Extent.Text }
    """
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=WALL_DIR, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_launcher_uses_discrete_separator_and_bare_subcommands():
    text = read("muse_wall_launcher.ps1")
    assert "'new-tab'" in text
    assert "'split-pane'" in text
    assert "';'" in text


def test_launcher_preserves_single_instance_attach():
    text = read("muse_wall_launcher.ps1")
    assert "'-w', '0'" in text


def test_launcher_guards_missing_terminal():
    assert "Get-Command wt.exe" in read("muse_wall_launcher.ps1")


def test_launcher_supports_staged_slot_counts():
    text = read("muse_wall_launcher.ps1")
    assert "ValidateSet(1, 4, 8, 16, 32, 64)" in text


def test_launcher_defaults_to_safe_monitor_mode():
    text = read("muse_wall_launcher.ps1")
    # Real Muse launch stays default-off until the CLI is verified on-machine.
    assert "[string]$SlotCommand = ''" in text
    # Default path still runs the state monitor, never a provider.
    assert "$python, $watcher, $title" in text
    assert "$python, $watcher, $paneTitle" in text


def test_launcher_gives_real_slots_their_own_workdir():
    text = read("muse_wall_launcher.ps1")
    assert 'runtime\\slots\\$title\\workdir' in text
    assert 'runtime\\slots\\$paneTitle\\workdir' in text


def test_wrappers_target_canonical_repo_root():
    for name in ("launch_wall.ps1", "status_wall.ps1", "stop_wall.ps1", "start_all.ps1"):
        text = read(name)
        assert "--root $PSScriptRoot" not in text, name
        assert "--root $scriptDir" not in text, name
        assert "Set-Location" in text, name


def test_supervisor_default_root_is_repo_root():
    text = (WALL_DIR / "supervisor.py").read_text(encoding="utf-8")
    assert "default=str(repo_root())" in text
    assert 'default=str(Path(__file__).parent)' not in text


def test_watcher_reads_canonical_state_first():
    text = (WALL_DIR / "watcher.py").read_text(encoding="utf-8")
    assert "resolve_state_file" in text
    assert 'parent.parent / "runtime" / "slots"' in text

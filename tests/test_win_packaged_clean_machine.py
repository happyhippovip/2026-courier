"""Contract for Rule 0 against the packaged Windows artifact.

The live process and uninstall proofs run on a GitHub-hosted Windows runner.
These checks run everywhere: they lock the harness environment, the CI-only
uninstall guard, and the workflow that builds with ``build_package.ps1``.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "win-packaged-clean-machine.yml"
HARNESS_FILE = Path(__file__).with_name("test_win_clean_machine_harness.py")

_SECRET_SAMPLE = "token=abc123secret\n" + ("ab" * 16) + "\n"


def _harness():
    spec = importlib.util.spec_from_file_location("win_clean_machine_harness_under_test", HARNESS_FILE)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {HARNESS_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_child_env_drops_system_python(tmp_path):
    """Packaged launch must not see the checkout or the runner's Python."""
    harness = _harness()
    base = {
        "PATH": r"C:\hostedtoolcache\Python\3.12.10\x64;C:\hostedtoolcache\Python\3.12.10\x64\Scripts",
        "Path": r"C:\hostedtoolcache\Python\3.12.10\x64",
        "PYTHONPATH": r"D:\a\courier\courier",
        "PythonPath": r"D:\a\courier\courier",
        "PYTHONHOME": r"C:\hostedtoolcache\Python\3.12.10\x64",
        "PYTHONSTARTUP": r"C:\startup.py",
        "VIRTUAL_ENV": r"C:\venv",
        "COURIER_HOME": r"C:\some-home",
        "SystemRoot": r"C:\Windows",
        "COURIER_API_KEY": "not-a-real-key",
        "COURIER_VERIFIER_API_KEY": "not-a-real-key",
    }
    env = harness.package_child_env(tmp_path, base)
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "VIRTUAL_ENV",
        "COURIER_HOME",
        "COURIER_API_KEY",
        "COURIER_VERIFIER_API_KEY",
        "Path",
        "PythonPath",
    ):
        assert name not in env, name
    assert "Python" not in env["PATH"]
    assert "hostedtoolcache" not in env["PATH"].lower()
    assert env["PATH"].split(";") == [
        r"C:\Windows\system32",
        r"C:\Windows",
        r"C:\Windows\System32\Wbem",
    ]
    assert env["LOCALAPPDATA"] == str(tmp_path)
    assert env["COURIER_TEST_NO_JOB"] == "1"
    assert env["SystemRoot"] == r"C:\Windows"


def test_packaged_root_follows_env(monkeypatch, tmp_path):
    harness = _harness()
    monkeypatch.delenv("COURIER_HARNESS_PACKAGE_DIR", raising=False)
    assert harness.packaged_root() is None
    monkeypatch.setenv("COURIER_HARNESS_PACKAGE_DIR", str(tmp_path / "missing"))
    with pytest.raises(AssertionError, match="COURIER_HARNESS_PACKAGE_DIR"):
        harness.packaged_root()
    monkeypatch.setenv("COURIER_HARNESS_PACKAGE_DIR", str(tmp_path))
    assert harness.packaged_root() == tmp_path.resolve()


def test_live_uninstall_requires_github_actions_and_explicit_flag(monkeypatch):
    """A workstation with CI=1 must not be treated as the throwaway runner."""
    harness = _harness()
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("COURIER_HARNESS_LIVE_UNINSTALL", raising=False)
    monkeypatch.setenv("CI", "true")
    assert harness.live_uninstall_permitted() is False
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert harness.live_uninstall_permitted() is False
    monkeypatch.setenv("COURIER_HARNESS_LIVE_UNINSTALL", "1")
    assert harness.live_uninstall_permitted() is True
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    assert harness.live_uninstall_permitted() is False


def test_evidence_stays_outside_the_working_tree_and_redacts(monkeypatch, tmp_path):
    harness = _harness()
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = repo / "evidence"
    monkeypatch.setenv("COURIER_HARNESS_EVIDENCE_DIR", str(inside))
    with pytest.raises(AssertionError, match="working tree"):
        harness.evidence_root(repo)
    outside = tmp_path / "outside"
    monkeypatch.setenv("COURIER_HARNESS_EVIDENCE_DIR", str(outside))
    assert harness.evidence_root(repo) == outside.resolve()
    harness.write_evidence("sample.txt", _SECRET_SAMPLE, repo=repo)
    written = (outside / "sample.txt").read_text(encoding="utf-8")
    assert "abc123secret" not in written
    assert "abababab" not in written
    assert "[redacted]" in written
    monkeypatch.delenv("COURIER_HARNESS_EVIDENCE_DIR", raising=False)
    harness.write_evidence("nope.txt", "x", repo=repo)
    assert not (repo / "nope.txt").exists()
    assert not (Path.cwd() / "nope.txt").exists()


def test_prove_live_uninstall_refuses_without_github_actions(monkeypatch, tmp_path):
    harness = _harness()
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("COURIER_HARNESS_LIVE_UNINSTALL", "1")
    with pytest.raises(AssertionError, match="refused"):
        harness.prove_live_uninstall(tmp_path)


def test_harness_uses_package_mode_without_repo_pythonpath():
    harness = _harness()
    source = HARNESS_FILE.read_text(encoding="utf-8")
    start = source.index("def test_win_clean_machine_harness")
    next_def = source.find("\ndef ", start + 1)
    body = source[start:] if next_def < 0 else source[start:next_def]
    assert "packaged_root()" in body
    assert "package_child_env(" in body
    assert "PYTHONPATH" in body
    # Repo mode still puts the checkout on PYTHONPATH. Package mode must not.
    assert "package_dir is not None" in body
    assert harness.package_child_env.__doc__


def test_workflow_reuses_build_package_and_publishes_short_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "windows-latest" in text
    assert "scripts/windows_worker/build_package.ps1" in text
    assert "COURIER_HARNESS_PACKAGE_DIR" in text
    assert "COURIER_HARNESS_LIVE_UNINSTALL" in text
    assert "COURIER_HARNESS_EVIDENCE_DIR" in text
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 3" in text
    assert "Remove-Item Env:PYTHONPATH" in text
    assert "Remove-Item Env:PYTHONHOME" in text
    assert "python.org" not in text
    assert "PyInstaller" not in text
    assert "Inno" not in text
    assert "install.ps1" not in text
    assert text.count("build_package.ps1") == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows uninstall proof")
def test_packaged_live_uninstall_preserves_user_data_on_ci_runner():
    """Rule 0 step 12 on the throwaway runner. Never runs on a dev machine."""
    harness = _harness()
    if not harness.live_uninstall_permitted():
        pytest.skip("live uninstall runs only on GITHUB_ACTIONS with COURIER_HARNESS_LIVE_UNINSTALL=1")
    package = harness.packaged_root()
    if package is None:
        pytest.fail("COURIER_HARNESS_PACKAGE_DIR is required for the live uninstall proof")
    result = harness.prove_live_uninstall(package)
    harness.write_evidence("uninstall.json", json.dumps(result, sort_keys=True) + "\n")
    assert result == {
        "config_removed": True,
        "courier_db_preserved": True,
        "logs_preserved": True,
        "program_dir_removed": True,
        "run_removed": True,
        "task_removed": True,
    }

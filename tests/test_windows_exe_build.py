"""Windows hub EXE: spec contract and smoke logic. No real Windows build on Linux.

The checked-in spec must name the hub's hidden imports and the static data
directory. The smoke starts a hub, reads /hub/api/status, and stops the
process group, including a child. Building CourierHub.exe is skipped unless
the host is Windows and PyInstaller is installed.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build():
    from scripts.build_windows_exe import (
        REQUIRED_DATA,
        REQUIRED_HIDDEN_IMPORTS,
        SPEC_PATH,
        audit_spec_text,
        build_windows_exe,
        main,
        smoke_hub,
        stop_process_group,
    )

    return {
        "REQUIRED_DATA": REQUIRED_DATA,
        "REQUIRED_HIDDEN_IMPORTS": REQUIRED_HIDDEN_IMPORTS,
        "SPEC_PATH": SPEC_PATH,
        "audit_spec_text": audit_spec_text,
        "build_windows_exe": build_windows_exe,
        "main": main,
        "smoke_hub": smoke_hub,
        "stop_process_group": stop_process_group,
    }


def test_spec_rejects_a_bundle_that_omits_static_data_and_journal():
    audit_spec_text = _build()["audit_spec_text"]
    missing = audit_spec_text("hiddenimports = ['courier_hub']\n")
    assert "courier_hub/static" in missing
    assert "courier_core.journal" in missing
    assert "courier_core.events" in missing
    assert "courier_core.state_machine" in missing


def test_checked_in_spec_names_hidden_imports_and_static_files():
    mod = _build()
    text = mod["SPEC_PATH"].read_text(encoding="utf-8")
    assert mod["audit_spec_text"](text) == []
    static = ROOT / "courier_hub" / "static"
    for name in ("index.html", "hub.js", "hub.css", "hub_core.mjs", "favicon.svg"):
        assert (static / name).is_file()
    assert ("courier_hub/static", "courier_hub/static") in mod["REQUIRED_DATA"]
    assert "courier_hub/__main__.py" in text
    assert "CourierHub" in text


def test_spec_enforces_unsigned_and_console_invariants():
    mod = _build()
    text = mod["SPEC_PATH"].read_text(encoding="utf-8")
    assert "codesign_identity=None" in text
    assert "upx=False" in text
    assert "console=True" in text
    assert 'excludes=["courier_overlay"]' in text
    assert 'name="CourierHub"' in text


def test_linux_build_skips_and_does_not_invent_an_exe(tmp_path):
    if sys.platform == "win32":
        pytest.skip("dieser Skip gilt für den Nicht-Windows-Host")
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is False
    assert result["skipped"] is True
    assert "Windows" in result["reason"]
    assert "PyInstaller" in result["reason"]
    assert list(tmp_path.rglob("*.exe")) == []


def test_non_windows_build_skips_and_does_not_invent_an_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is False
    assert result["skipped"] is True
    assert "Windows" in result["reason"]
    assert list(tmp_path.rglob("*.exe")) == []


def test_windows_build_skips_cleanly_when_pyinstaller_is_absent(tmp_path):
    if shutil.which("pyinstaller") is not None or importlib.util.find_spec("PyInstaller") is not None:
        pytest.skip("Dieser Test prüft den echten Skip-Pfad wenn PyInstaller fehlt")
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is False
    assert result["skipped"] is True
    assert "PyInstaller ist nicht installiert" in result["reason"]
    assert result["exe"] is None
    assert list(tmp_path.rglob("*.exe")) == []


def test_windows_build_pyinstaller_absent_fallback_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is False
    assert result["skipped"] is True
    assert "PyInstaller ist nicht installiert" in result["reason"]
    assert result["exe"] is None
    assert list(tmp_path.rglob("*.exe")) == []


def test_build_windows_exe_cli_check_and_skip_contract(tmp_path, monkeypatch, capsys):
    main = _build()["main"]
    # 1. --check with valid spec
    code = main(["--check"])
    assert code == 0
    captured = capsys.readouterr()
    assert "SPEC OK" in captured.out

    # 2. --check with invalid spec text
    monkeypatch.setattr(
        _build()["SPEC_PATH"].__class__,
        "read_text",
        lambda self, encoding="utf-8": "hiddenimports = []\n"
    )
    code_bad = main(["--check"])
    assert code_bad == 1
    captured_bad = capsys.readouterr()
    assert "SPEC MISSING" in captured_bad.out


def test_build_windows_exe_cli_skip_when_pyinstaller_missing(tmp_path, monkeypatch, capsys):
    main = _build()["main"]
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    code = main(["--dist", str(tmp_path / "dist")])
    assert code == 2
    captured = capsys.readouterr()
    assert "SKIP: PyInstaller ist nicht installiert" in captured.out


@pytest.mark.skipif(
    sys.platform != "win32" or (shutil.which("pyinstaller") is None and importlib.util.find_spec("PyInstaller") is None),
    reason=(
        "Echter Windows-EXE-Build braucht Windows und ein lokales PyInstaller. "
        "Dieser Host ist kein Windows oder hat kein PyInstaller installiert."
    ),
)
def test_windows_exe_builds_and_answers(tmp_path):
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is True
    exe = Path(result["exe"])
    assert exe.is_file()
    body = _build()["smoke_hub"](
        [str(exe), "--home", str(tmp_path / "home"), "--controller", "http://127.0.0.1:9",
         "--port", "0", "--print-url"],
        home=tmp_path / "home",
    )
    assert body["controller"] == "not_set_up"


def test_source_hub_answers_status_and_then_stops(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    body = _build()["smoke_hub"](
        [sys.executable, "-m", "courier_hub", "--home", str(home),
         "--controller", "http://127.0.0.1:9", "--port", "0", "--print-url"],
        home=home,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        cwd=ROOT,
    )
    assert body["controller"] == "not_set_up"
    assert "checked_at" in body


def test_stop_kills_the_child_process(tmp_path):
    stop_process_group = _build()["stop_process_group"]
    script = tmp_path / "parent.py"
    script.write_text(textwrap.dedent("""
        import subprocess, sys, time
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        print("child %s" % child.pid, flush=True)
        time.sleep(120)
    """), encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    line = proc.stdout.readline()
    child_pid = int(line.split()[1])
    try:
        stop_process_group(proc)
        proc.wait(timeout=5)
        assert proc.poll() is not None
        alive = _pid_alive(child_pid)
        assert alive is False
    finally:
        if proc.poll() is None:
            stop_process_group(proc)


def test_stop_process_group_is_idempotent_when_process_already_exited(tmp_path):
    stop_process_group = _build()["stop_process_group"]
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait(timeout=5)
    assert proc.poll() is not None
    # Must not raise when called on an already terminated process
    stop_process_group(proc)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            try:
                res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, check=False)
                return str(pid) in res.stdout
            except Exception:
                return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

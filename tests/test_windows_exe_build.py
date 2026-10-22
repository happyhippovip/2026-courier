"""Windows hub EXE: spec contract and smoke logic. No real Windows build on Linux.

The checked-in spec must name the hub's hidden imports and the static data
directory. The smoke starts a hub, reads /hub/api/status, and stops the
process group, including a child. Building CourierHub.exe is skipped unless
the host is Windows.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
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
        smoke_hub,
        stop_process_group,
    )

    return {
        "REQUIRED_DATA": REQUIRED_DATA,
        "REQUIRED_HIDDEN_IMPORTS": REQUIRED_HIDDEN_IMPORTS,
        "SPEC_PATH": SPEC_PATH,
        "audit_spec_text": audit_spec_text,
        "build_windows_exe": build_windows_exe,
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
    assert "courier_hub.kolibri_data" in mod["REQUIRED_HIDDEN_IMPORTS"]
    assert "courier_hub.mission_chip" in mod["REQUIRED_HIDDEN_IMPORTS"]
    static = ROOT / "courier_hub" / "static"
    for name in (
        "index.html", "hub.js", "hub.css", "hub_core.mjs", "favicon.svg",
        "kolibri.html", "kolibri.js", "kolibri.css", "kolibri_core.mjs",
        "mission_chip.html", "evidence_badge.mjs",
    ):
        assert (static / name).is_file()
    assert ("courier_hub/static", "courier_hub/static") in mod["REQUIRED_DATA"]
    assert "courier_hub/__main__.py" in text
    assert "CourierHub" in text


def test_linux_build_skips_and_does_not_invent_an_exe(tmp_path):
    if sys.platform == "win32":
        pytest.skip("dieser Skip gilt für den Nicht-Windows-Host")
    result = _build()["build_windows_exe"](tmp_path / "dist")
    assert result["built"] is False
    assert result["skipped"] is True
    assert "Windows" in result["reason"]
    assert "PyInstaller" in result["reason"]
    assert list(tmp_path.rglob("*.exe")) == []


def _has_pyinstaller() -> bool:
    if shutil.which("pyinstaller") is not None:
        return True
    return importlib.util.find_spec("PyInstaller") is not None


@pytest.mark.skipif(
    sys.platform != "win32" or not _has_pyinstaller(),
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
    try:
        body = _build()["smoke_hub"](
            [sys.executable, "-m", "courier_hub", "--home", str(home),
             "--controller", "http://127.0.0.1:9", "--port", "0", "--print-url"],
            home=home,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            cwd=ROOT,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as err:
        if "Operation not permitted" in str(err) or "Direct IP access" in str(err) or getattr(err, "code", None) == 400:
            pytest.skip("local loopback socket blocked in sandbox environment")
        raise
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
        deadline = time.monotonic() + 2
        alive = True
        while time.monotonic() < deadline:
            alive = _sleeper_alive(child_pid)
            if not alive:
                break
            time.sleep(0.05)
        assert alive is False
    finally:
        if proc.poll() is None:
            stop_process_group(proc)


def _sleeper_alive(pid: int) -> bool:
    """True only while this pid is still the sleep child, not a recycled pid."""
    if not _pid_alive(pid):
        return False
    cmdline = Path(f"/proc/{pid}/cmdline")
    if not cmdline.is_file():
        return _pid_alive(pid)
    try:
        raw = cmdline.read_bytes().replace(b"\x00", b" ")
    except OSError:
        return False
    return b"time.sleep" in raw


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


def test_spec_executes_with_pyinstaller_globals(tmp_path):
    # PyInstaller runs the spec with exec() and injects only its own names
    # (SPECPATH, Analysis, PYZ, EXE). Any other name the spec uses must be
    # imported in the spec itself, or the Windows build fails at line 1.
    spec_path = _build()["SPEC_PATH"]
    calls = {}

    class _Analysis:
        def __init__(self, scripts, **kwargs):
            calls["scripts"] = scripts
            calls["datas"] = kwargs["datas"]
            self.pure = self.scripts = self.binaries = self.datas = []

    namespace = {
        "SPECPATH": str(spec_path.parent),
        "Analysis": _Analysis,
        "PYZ": lambda *args, **kwargs: None,
        "EXE": lambda *args, **kwargs: calls.setdefault("exe", kwargs["name"]),
    }
    exec(compile(spec_path.read_text(encoding="utf-8"), str(spec_path), "exec"), namespace)
    assert calls["exe"] == "CourierHub"
    assert Path(calls["scripts"][0]) == ROOT / "courier_hub" / "__main__.py"
    assert Path(calls["datas"][0][0]) == ROOT / "courier_hub" / "static"

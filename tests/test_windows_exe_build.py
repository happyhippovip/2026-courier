"""Windows hub EXE: spec contract and smoke logic. No real Windows build on Linux.

The checked-in spec must name the hub's hidden imports and the static data
directory. The smoke starts a hub, reads /hub/api/status, and stops the
process group, including a child. Building CourierHub.exe is skipped unless
the host is Windows.
"""
import os
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
    static = ROOT / "courier_hub" / "static"
    for name in ("index.html", "hub.js", "hub.css", "hub_core.mjs", "favicon.svg"):
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


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "Echter Windows-EXE-Build braucht Windows und ein lokales PyInstaller. "
        "Dieser Host ist kein Windows. Es wird kein CourierHub.exe erzeugt und keiner behauptet."
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


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "mac_worker" / "install.sh"


def test_installer_resolves_project_from_its_own_location(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    launchctl = fake_bin / "launchctl"
    launchctl.write_text("#!/bin/sh\nexit 0\n")
    launchctl.chmod(0o755)
    python = fake_bin / "python3"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)

    unrelated_cwd = tmp_path / "unrelated"
    unrelated_cwd.mkdir()
    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    completed = subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=unrelated_cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    plist = home / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist"
    content = plist.read_text()
    assert "TARGET_DIR" not in content
    assert "PYTHON_BIN" not in content
    assert str(ROOT) in content
    assert str(python) in content


def test_installer_refuses_broken_runtime_before_launchd_registration(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    launch_marker = tmp_path / "launchctl-called"
    launchctl = fake_bin / "launchctl"
    launchctl.write_text(f"#!/bin/sh\ntouch '{launch_marker}'\n")
    launchctl.chmod(0o755)
    python = fake_bin / "python3"
    python.write_text("#!/bin/sh\nexit 1\n")
    python.chmod(0o755)

    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    completed = subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode != 0
    assert "refusing to register a broken launchd worker" in completed.stderr
    assert not launch_marker.exists()
    assert not (home / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist").exists()

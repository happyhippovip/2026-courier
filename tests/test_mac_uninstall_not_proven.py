"""uninstall.sh must not report success when the plist is still there.

This host has no launchctl. The test does not claim a launchd unload.
"""
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mac_worker" / "uninstall.sh"


def run(home):
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(["bash", str(SCRIPT)], text=True, capture_output=True, env=env)


def test_failed_removal_is_not_uninstalled(tmp_path):
    plist = tmp_path / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist"
    plist.mkdir(parents=True)
    result = run(tmp_path)
    assert result.returncode != 0
    assert "Mac worker uninstalled." not in result.stdout
    assert plist.exists()


def test_removed_plist_is_uninstalled(tmp_path):
    plist = tmp_path / "Library" / "LaunchAgents" / "com.courier.mac_worker.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("not-a-launchd-proof\n")
    plist.chmod(stat.S_IRUSR | stat.S_IWUSR)
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Mac worker uninstalled." in result.stdout
    assert not plist.exists()


def test_missing_plist_is_already_absent(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Mac worker uninstalled." in result.stdout

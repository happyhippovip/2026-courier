"""courier_restart.sh must not report Restarted when launchctl did not unload a job."""

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "courier_restart.sh"

STUB = """#!/bin/sh
if [ "$1" = "list" ]; then
  if [ -f "$LIST_FILE" ]; then
    cat "$LIST_FILE"
  fi
  exit "${LIST_RC:-0}"
fi
if [ "$1" = "unload" ]; then
  printf '%s\\n' "$*" >> "$LAUNCHCTL_LOG"
  exit "${UNLOAD_RC:-0}"
fi
echo "unexpected launchctl $*" >&2
exit 1
"""


def _path_without_real_launchctl(tmp_path: Path, stub: bool) -> Path:
    bind = tmp_path / "bin"
    bind.mkdir()
    for src in (Path("/bin"), Path("/usr/bin")):
        if not src.is_dir():
            continue
        for child in src.iterdir():
            if child.name == "launchctl" or not child.exists():
                continue
            dest = bind / child.name
            if dest.exists():
                continue
            dest.symlink_to(child)
    if stub:
        exe = bind / "launchctl"
        exe.write_text(STUB, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return bind


def _run(tmp_path: Path, *, stub: bool, listing: str = "", list_rc: int = 0, unload_rc: int = 0):
    home = tmp_path / "home"
    home.mkdir()
    list_file = tmp_path / "list.txt"
    if listing:
        list_file.write_text(listing, encoding="utf-8")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = str(_path_without_real_launchctl(tmp_path, stub))
    env["LIST_FILE"] = str(list_file)
    env["LIST_RC"] = str(list_rc)
    env["UNLOAD_RC"] = str(unload_rc)
    env["LAUNCHCTL_LOG"] = str(tmp_path / "launchctl.log")
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc, home


def test_missing_launchctl_is_not_restarted(tmp_path):
    proc, _home = _run(tmp_path, stub=False)
    assert proc.returncode != 0
    assert "Restarted." not in proc.stdout
    assert "not proven" in proc.stderr


def test_no_courier_job_is_not_restarted(tmp_path):
    proc, _home = _run(tmp_path, stub=True, listing="123 0 com.example.other\n")
    assert proc.returncode != 0
    assert "Restarted." not in proc.stdout
    assert "not proven" in proc.stderr


def test_failed_unload_is_not_restarted(tmp_path):
    proc, _home = _run(
        tmp_path,
        stub=True,
        listing="123 0 com.courier.server\n",
        unload_rc=1,
    )
    assert proc.returncode != 0
    assert "Restarted." not in proc.stdout
    assert "not proven" in proc.stderr


def test_unloaded_job_is_restarted(tmp_path):
    proc, home = _run(tmp_path, stub=True, listing="123 0 com.courier.server\n")
    assert proc.returncode == 0, proc.stderr
    assert "Restarted." in proc.stdout
    log = (tmp_path / "launchctl.log").read_text(encoding="utf-8")
    assert f"{home}/Library/LaunchAgents/com.courier.server.plist" in log

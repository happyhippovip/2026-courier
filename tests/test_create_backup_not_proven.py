"""create_backup.sh must not call a failed tar a completed backup."""

import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_backup.sh"


def _fixture(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    dest = scripts / "create_backup.sh"
    shutil.copy(SCRIPT, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "app.txt").write_text("state", encoding="utf-8")
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "unit.txt").write_text("cfg", encoding="utf-8")
    return dest


def _run(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_unreadable_input_is_not_a_completed_backup(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root bypasses mode 000, so this host cannot show the tar failure")
    script = _fixture(tmp_path)
    locked = tmp_path / "server" / "locked"
    locked.mkdir()
    (locked / "secret.txt").write_text("nope", encoding="utf-8")
    os.chmod(locked, 0)
    try:
        proc = _run(script)
    finally:
        os.chmod(locked, 0o755)
    assert proc.returncode != 0
    assert "Backup completed successfully!" not in proc.stdout
    assert "Backup not proven." in proc.stderr
    backups = tmp_path / "backups"
    archives = list(backups.glob("*.tar.gz")) if backups.exists() else []
    assert archives == []


def test_present_paths_are_archived_when_tar_succeeds(tmp_path):
    script = _fixture(tmp_path)
    proc = _run(script)
    assert proc.returncode == 0, proc.stderr
    assert "Backup completed successfully!" in proc.stdout
    archives = list((tmp_path / "backups").glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        names = archive.getnames()
    assert "server/app.txt" in names
    assert "deploy/unit.txt" in names
    assert ".env*" not in names
    assert "*.py" not in names
    assert "*.sh" not in names

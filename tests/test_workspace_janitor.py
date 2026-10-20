"""Tests for courier_core.workspace_janitor (Scratch Workspace Garbage Collector & Leak Patrol)."""

import json
import os
import time
import pytest
from pathlib import Path
from courier_core.workspace_janitor import (
    WorkspaceJanitor,
    WorkspaceTarget,
    JanitorReport,
    main,
)


def test_detect_and_prune_stale_scratch_directory(tmp_path):
    scratch_root = tmp_path / "scratch"
    scratch_root.mkdir()

    # Create orphaned directory with non-existent PID
    orphaned_dir = scratch_root / "job_dead_123"
    orphaned_dir.mkdir()
    (orphaned_dir / "temp_payload.bin").write_bytes(b"A" * 1024)
    (orphaned_dir / "owner.pid").write_text("99999999", encoding="utf-8")  # Non-existent PID

    janitor = WorkspaceJanitor(target_roots=[str(scratch_root)], max_age_seconds=0)
    targets = janitor.scan()

    assert len(targets) == 1
    assert targets[0].is_orphaned is True
    assert targets[0].bytes_size >= 1024

    report = janitor.prune(dry_run=False)
    assert report.dirs_removed == 1
    assert report.bytes_reclaimed >= 1024
    assert not orphaned_dir.exists()


def test_preserve_active_workspace_with_living_pid(tmp_path):
    scratch_root = tmp_path / "scratch"
    scratch_root.mkdir()

    # Create active directory with current living PID
    active_dir = scratch_root / "job_live_456"
    active_dir.mkdir()
    (active_dir / "active.dat").write_bytes(b"B" * 512)
    (active_dir / "owner.pid").write_text(str(os.getpid()), encoding="utf-8")

    janitor = WorkspaceJanitor(target_roots=[str(scratch_root)], max_age_seconds=3600)
    targets = janitor.scan()

    assert len(targets) == 1
    assert targets[0].is_orphaned is False

    report = janitor.prune(dry_run=False)
    assert report.dirs_removed == 0
    assert active_dir.exists()


def test_stale_lockfile_pruning(tmp_path):
    lock_root = tmp_path / "locks"
    lock_root.mkdir()

    # Create stale lock file older than TTL
    stale_lock = lock_root / "stale_task.lock"
    stale_lock.write_text(json.dumps({"pid": 99999999, "created_at": time.time() - 500}), encoding="utf-8")

    janitor = WorkspaceJanitor(target_roots=[str(lock_root)], max_age_seconds=60)
    report = janitor.prune(dry_run=False)

    assert report.stale_locks_cleared == 1
    assert not stale_lock.exists()


def test_dry_run_mode_safety(tmp_path):
    scratch_root = tmp_path / "scratch"
    scratch_root.mkdir()
    dead_dir = scratch_root / "orphan_dry"
    dead_dir.mkdir()
    (dead_dir / "owner.pid").write_text("99999999", encoding="utf-8")

    janitor = WorkspaceJanitor(target_roots=[str(scratch_root)], max_age_seconds=0)
    report = janitor.prune(dry_run=True)

    assert report.dirs_removed == 1  # Identified for removal
    assert dead_dir.exists()  # Not deleted in dry run


def test_protected_baseline_exemption(tmp_path):
    # Root containing protected keyword
    protected_dir = tmp_path / "checkpoints_fake"
    protected_dir.mkdir()
    (protected_dir / "data.txt").write_text("safe", encoding="utf-8")

    janitor = WorkspaceJanitor(target_roots=[str(protected_dir)])
    targets = janitor.scan()

    # Must be completely skipped due to protected baseline safety rule
    assert len(targets) == 0


def test_cli_workspace_janitor(tmp_path, capsys):
    scratch_root = tmp_path / "cli_scratch"
    scratch_root.mkdir()
    dead = scratch_root / "dead_job"
    dead.mkdir()
    (dead / "owner.pid").write_text("99999999", encoding="utf-8")

    # Scan CLI
    rc1 = main(["scan", "--root", str(scratch_root)])
    assert rc1 == 0
    assert "SCANNED" in capsys.readouterr().out

    # Report CLI (dry-run forensic JSON report before pruning)
    rc_rep = main(["report", "--root", str(scratch_root)])
    assert rc_rep == 0
    rep_json = json.loads(capsys.readouterr().out)
    assert rep_json["summary"]["dirs_removed"] == 1
    assert dead.exists()

    # Prune CLI
    rc2 = main(["prune", "--root", str(scratch_root)])
    assert rc2 == 0
    assert "PRUNED" in capsys.readouterr().out
    assert not dead.exists()


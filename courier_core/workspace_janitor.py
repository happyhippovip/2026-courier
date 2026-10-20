"""Ephemeral Scratch Workspace Garbage Collector and Leak Patrol for Courier Symphony.

Scans for abandoned worker scratch directories, dead-process temporary workspaces,
and stale lock files, reclaiming disk space while strictly protecting baseline repositories.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, List, Optional


PROTECTED_PATTERNS = {
    "checkpoints",
    "registries",
    "courier_core",
    "courier_v3",
    "courier_hub",
    "courier_worker",
    "_courier-recovery",
    "courier_backups",
    ".git",
    "tests",
}


def _is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently active on the host OS."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, SystemError):
        return False


def _get_dir_size(p: Path) -> int:
    """Calculate total byte size of a directory recursively."""
    total = 0
    try:
        for entry in p.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


@dataclass
class WorkspaceTarget:
    path: str
    is_dir: bool
    bytes_size: int
    is_orphaned: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JanitorReport:
    dirs_removed: int
    bytes_reclaimed: int
    stale_locks_cleared: int
    active_preserved: int
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorkspaceJanitor:
    """Garbage collector and patrol engine for ephemeral run and scratch spaces."""

    def __init__(
        self,
        target_roots: Optional[List[str]] = None,
        max_age_seconds: float = 3600.0,
    ):
        self.target_roots = [Path(r) for r in (target_roots or ["run/scratch", "run"])]
        self.max_age_seconds = max_age_seconds

    def _is_protected(self, path: Path) -> bool:
        """Verify if a path belongs to the protected baseline repository."""
        parts = {p.lower() for p in path.parts}
        for pat in PROTECTED_PATTERNS:
            if pat in parts or any(pat in part for part in parts):
                return True
        return False

    def scan(self) -> List[WorkspaceTarget]:
        """Scan target roots for orphaned workspaces and stale lock files."""
        targets: List[WorkspaceTarget] = []
        now = time.time()

        for root in self.target_roots:
            if not root.exists() or self._is_protected(root):
                continue

            for item in root.iterdir():
                if self._is_protected(item):
                    continue

                if item.is_dir():
                    size = _get_dir_size(item)
                    pid_file = item / "owner.pid"
                    is_orphaned = False
                    reason = "Active workspace"

                    if pid_file.exists():
                        try:
                            owner_pid = int(pid_file.read_text(encoding="utf-8").strip())
                            if not _is_pid_alive(owner_pid):
                                is_orphaned = True
                                reason = f"Owner process {owner_pid} is terminated"
                        except Exception:
                            is_orphaned = True
                            reason = "Corrupted owner.pid"
                    else:
                        age = now - item.stat().st_mtime
                        if age > self.max_age_seconds:
                            is_orphaned = True
                            reason = f"Age ({age:.0f}s) exceeds TTL ({self.max_age_seconds:.0f}s) without owner PID"

                    targets.append(WorkspaceTarget(
                        path=str(item),
                        is_dir=True,
                        bytes_size=size,
                        is_orphaned=is_orphaned,
                        reason=reason,
                    ))

                elif item.is_file() and item.name.endswith(".lock"):
                    size = item.stat().st_size
                    is_orphaned = False
                    reason = "Active lock"

                    try:
                        content = item.read_text(encoding="utf-8").strip()
                        lock_data = json.loads(content)
                        lock_pid = lock_data.get("pid")
                        lock_created = lock_data.get("created_at", 0)

                        if lock_pid and not _is_pid_alive(int(lock_pid)):
                            is_orphaned = True
                            reason = f"Lock owner PID {lock_pid} is dead"
                        elif now - lock_created > self.max_age_seconds:
                            is_orphaned = True
                            reason = "Lock expired"
                    except Exception:
                        age = now - item.stat().st_mtime
                        if age > self.max_age_seconds:
                            is_orphaned = True
                            reason = "Lock expired (non-JSON)"

                    targets.append(WorkspaceTarget(
                        path=str(item),
                        is_dir=False,
                        bytes_size=size,
                        is_orphaned=is_orphaned,
                        reason=reason,
                    ))

        return targets

    def prune(self, dry_run: bool = False) -> JanitorReport:
        """Prune identified orphaned scratch spaces and stale locks."""
        targets = self.scan()
        dirs_removed = 0
        bytes_reclaimed = 0
        stale_locks = 0
        active_preserved = 0

        for t in targets:
            p = Path(t.path)
            if not t.is_orphaned:
                active_preserved += 1
                continue

            if t.is_dir:
                dirs_removed += 1
                bytes_reclaimed += t.bytes_size
                if not dry_run:
                    shutil.rmtree(p, ignore_errors=True)
            else:
                stale_locks += 1
                bytes_reclaimed += t.bytes_size
                if not dry_run:
                    try:
                        p.unlink(missing_ok=True)
                    except OSError:
                        pass

        return JanitorReport(
            dirs_removed=dirs_removed,
            bytes_reclaimed=bytes_reclaimed,
            stale_locks_cleared=stale_locks,
            active_preserved=active_preserved,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Workspace Janitor CLI")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # scan
    p_sc = sub.add_parser("scan", help="Scan for orphaned scratch directories")
    p_sc.add_argument("--root", default="run/scratch", help="Target root directory")

    # prune
    p_pr = sub.add_parser("prune", help="Prune orphaned scratch spaces")
    p_pr.add_argument("--root", default="run/scratch", help="Target root directory")
    p_pr.add_argument("--dry-run", action="store_true", help="Simulate prune without deleting")

    # report
    p_rep = sub.add_parser("report", help="Generate forensic cleanup audit report")
    p_rep.add_argument("--root", default="run/scratch", help="Target root directory")

    args = parser.parse_args(argv)
    janitor = WorkspaceJanitor(target_roots=[args.root], max_age_seconds=0)

    if args.subcommand == "scan":
        targets = janitor.scan()
        print(f"SCANNED {len(targets)} targets in {args.root}:")
        for t in targets:
            status = "ORPHANED" if t.is_orphaned else "ACTIVE"
            print(f" [{status}] {t.path} ({t.bytes_size} bytes): {t.reason}")
        return 0

    elif args.subcommand == "prune":
        rep = janitor.prune(dry_run=args.dry_run)
        print(f"PRUNED {rep.dirs_removed} directories and {rep.stale_locks_cleared} locks (reclaimed {rep.bytes_reclaimed} bytes)")
        return 0

    elif args.subcommand == "report":
        rep = janitor.prune(dry_run=True)
        targets = janitor.scan()
        print(json.dumps({
            "summary": rep.to_dict(),
            "targets": [t.to_dict() for t in targets],
        }, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

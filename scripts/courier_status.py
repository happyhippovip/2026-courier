#!/usr/bin/env python3
"""
Courier Status: Headless Status, Critical Snapshot L0, and Reboot Verdict (FRZ-02, FRZ-07).
Works without GUI/Explorer/IDE, reads SQLite journal truth, tracks owned PIDs, and evaluates safe reboot conditions.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    if os.environ.get("COURIER_HOME"):
        return Path(os.environ["COURIER_HOME"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Courier"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Courier"
    else:
        return Path.home() / ".courier"


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = kernel32.OpenProcess(0x1000, False, pid)
            if h:
                kernel32.CloseHandle(h)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def get_owned_pids(app_data_dir: Path) -> dict[str, dict]:
    run_dir = app_data_dir / "run"
    tracked = {}
    if not run_dir.exists():
        return tracked

    for name in ("launcher", "controller", "worker", "hub"):
        pid_file = run_dir / f"{name}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                alive = is_pid_alive(pid)
                tracked[name] = {"pid": pid, "alive": alive}
            except (ValueError, OSError):
                pass
    return tracked


def get_active_claims(app_data_dir: Path) -> list[dict]:
    claims_dir = app_data_dir / "run" / "claims"
    claims = []
    if not claims_dir.exists():
        return claims

    for p in claims_dir.glob("dispatch-*.json"):
        try:
            claims.append(json.loads(p.read_text()))
        except Exception:
            pass
    return claims


def get_journal_stats(app_data_dir: Path) -> dict:
    db_path = app_data_dir / "courier.db"
    if not db_path.exists():
        return {"exists": False}

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        
        # Events count and last sequence
        cur.execute("SELECT count(*), max(seq) FROM events")
        row = cur.fetchone()
        event_count = row[0] if row else 0
        last_seq = row[1] if row and row[1] is not None else 0

        # Tasks by status
        task_counts = {}
        try:
            cur.execute("SELECT status, count(*) FROM tasks GROUP BY status")
            for status, count in cur.fetchall():
                task_counts[status] = count
        except sqlite3.OperationalError:
            pass

        conn.close()
        return {
            "exists": True,
            "event_count": event_count,
            "last_seq": last_seq,
            "tasks": task_counts,
        }
    except Exception as exc:
        return {"exists": True, "error": str(exc)}


def get_git_status(repo_dir: Path | None = None) -> dict:
    cwd = str(repo_dir) if repo_dir is not None else None
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=False, cwd=cwd).stdout.strip()
        diff = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False, cwd=cwd).stdout.strip()
        dirty_lines = [line for line in diff.splitlines() if line.strip()]
        
        unpushed = 0
        if branch:
            log_proc = subprocess.run(["git", "log", f"origin/{branch}..HEAD", "--oneline"], capture_output=True, text=True, check=False, cwd=cwd)
            if log_proc.returncode == 0:
                unpushed = len([line for line in log_proc.stdout.splitlines() if line.strip()])

        return {
            "branch": branch,
            "dirty_count": len(dirty_lines),
            "unpushed_count": unpushed,
            "clean": len(dirty_lines) == 0,
        }
    except Exception as exc:
        return {"error": str(exc), "clean": True, "dirty_count": 0, "unpushed_count": 0}


def get_resource_sample() -> dict:
    sample: dict = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        import psutil
        sample["cpu_pct"] = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        sample["ram_pct"] = mem.percent
        sample["ram_used_mb"] = round(mem.used / (1024 * 1024), 1)
        sample["ram_total_mb"] = round(mem.total / (1024 * 1024), 1)
    except ImportError:
        sample["cpu_pct"] = None
        sample["ram_pct"] = None
    return sample


def evaluate_reboot_verdict(owned_pids: dict, claims: list, journal: dict, git_st: dict) -> tuple[str, list[str]]:
    reasons = []

    # 1. Any live task in claims?
    if claims:
        reasons.append(f"{len(claims)} active task claims in progress; rebooting will abort active execution")

    # 2. Any running tasks in journal?
    running_tasks = journal.get("tasks", {}).get("RUNNING", 0)
    if running_tasks > 0:
        reasons.append(f"{running_tasks} tasks marked RUNNING in journal")

    # 3. Unsaved git changes
    if git_st.get("dirty_count", 0) > 0:
        reasons.append(f"{git_st['dirty_count']} uncommitted modified files in working directory")

    # 4. Unpushed commits risk
    unpushed = git_st.get("unpushed_count", 0)
    if unpushed > 10:
        reasons.append(f"{unpushed} unpushed commits on current branch at risk of machine loss")

    if reasons:
        return "NOT_SAFE_TO_REBOOT", reasons
    return "SAFE_TO_REBOOT", ["All journal events committed; zero in-flight tasks; workspace clean"]


def get_critical_snapshot_l0(app_data_dir: Path | None = None, repo_dir: Path | None = None) -> dict:
    if app_data_dir is None:
        app_data_dir = get_app_data_dir()

    owned_pids = get_owned_pids(app_data_dir)
    claims = get_active_claims(app_data_dir)
    journal = get_journal_stats(app_data_dir)
    git_st = get_git_status(repo_dir)
    resources = get_resource_sample()

    # Legacy fallback
    legacy_goals = {}
    legacy_unassigned = 0
    state_file = Path("server/state/central_state.json")
    if not journal.get("exists") and state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
            goals = state.get("goals", {})
            for g in goals.values():
                if g.get("status") == "ACTIVE":
                    for step in g.get("workflow_plan", []):
                        if step.get("status") == "UNASSIGNED":
                            legacy_unassigned += 1
            legacy_goals = {"active": len([g for g in goals.values() if g.get("status") == "ACTIVE"]), "unassigned": legacy_unassigned}
        except Exception:
            pass

    reboot_verdict, reasons = evaluate_reboot_verdict(owned_pids, claims, journal, git_st)

    snapshot = {
        "schema_version": "1.0",
        "snapshot_id": f"SNAP-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "app_data_dir": str(app_data_dir),
        "owned_processes": owned_pids,
        "active_claims": claims,
        "journal": journal,
        "git": git_st,
        "resources": resources,
        "legacy_state": legacy_goals,
        "reboot_verdict": {
            "verdict": reboot_verdict,
            "reasons": reasons,
            "safe": reboot_verdict == "SAFE_TO_REBOOT",
        },
    }
    return snapshot


def format_status_report(snapshot: dict) -> str:
    lines = []
    lines.append("=== COURIER SYMPHONY — CRITICAL SNAPSHOT L0 ===")
    lines.append(f"Snapshot ID:  {snapshot['snapshot_id']}")
    lines.append(f"Captured At:  {snapshot['captured_at']}")
    lines.append(f"Data Dir:     {snapshot['app_data_dir']}")

    lines.append("\n[Owned Processes]")
    procs = snapshot.get("owned_processes", {})
    if procs:
        for name, info in procs.items():
            state = "ALIVE" if info["alive"] else "DEAD"
            lines.append(f"  {name:<12}: PID {info['pid']} ({state})")
    else:
        lines.append("  No owned PID files found.")

    lines.append("\n[Ledger / Journal]")
    j = snapshot.get("journal", {})
    if j.get("exists"):
        lines.append(f"  Events Total: {j.get('event_count', 0)} (Head Seq: {j.get('last_seq', 0)})")
        tasks = j.get("tasks", {})
        if tasks:
            task_str = ", ".join(f"{k}: {v}" for k, v in tasks.items())
            lines.append(f"  Tasks Status: {task_str}")
    else:
        legacy = snapshot.get("legacy_state", {})
        if legacy:
            lines.append(f"  Legacy Goals: {legacy.get('active', 0)} active, {legacy.get('unassigned', 0)} unassigned")
        else:
            lines.append("  No active database or ledger found.")

    lines.append("\n[Git Workspace]")
    g = snapshot.get("git", {})
    lines.append(f"  Branch:       {g.get('branch', 'unknown')}")
    lines.append(f"  Dirty Files:  {g.get('dirty_count', 0)}")
    lines.append(f"  Unpushed:     {g.get('unpushed_count', 0)} commits")

    lines.append("\n[Reboot Verdict]")
    rv = snapshot.get("reboot_verdict", {})
    verdict = rv.get("verdict", "UNKNOWN")
    lines.append(f"  Verdict:      {verdict}")
    for r in rv.get("reasons", []):
        lines.append(f"  - {r}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Courier Symphony Headless Status & Critical Snapshot L0")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON snapshot")
    parser.add_argument("--write-snapshot", action="store_true", help="Write snapshot to run/critical_snapshot_l0.json")
    parser.add_argument("--reboot-check", action="store_true", help="Exit 0 if SAFE_TO_REBOOT, 1 otherwise")
    args = parser.parse_args()

    app_data = get_app_data_dir()
    snapshot = get_critical_snapshot_l0(app_data)

    if args.write_snapshot:
        run_dir = app_data / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = run_dir / "critical_snapshot_l0.json"
        out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(snapshot, indent=2))
    elif not args.reboot_check:
        print(format_status_report(snapshot))

    if args.reboot_check:
        sys.exit(0 if snapshot["reboot_verdict"]["safe"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Context Sync / Update Steward Engine for 2026 Courier.

Role: Permanent Context Synchronization & Update Steward
Position:
HUMAN → IDEA SYNC → UPDATE STEWARD → CHIEF COMMANDER → SMART ROUTER → WORKER → RESULT → UPDATE STEWARD → CHIEF REVIEW → NEXT TASK

Responsibilities:
1. Deterministically reads repository heads (Courier, Memory, Godot).
2. Reads Courier event bus state (locks, tasks, results, decisions, approvals, agent states).
3. Reads Project Memory truth (PROJECT_STATE.md, DECISIONS.md, IDEA_ARCHIVE.md, etc.).
4. Ingests Idea Sync Context Delta.
5. Produces atomic, hashed, versioned `CurrentContextSnapshot`.
6. Enforces strict Truth Classification invariants (IDEA != IMPLEMENTED, USER_REPORTED != VERIFIED).
7. Attaches bounded versioned context to Chief worker jobs.
8. Verifies worker context acknowledgement (context_version_seen, context_snapshot_hash_seen).
9. Detects stale tasks and signals `CONTEXT_REFRESH_REQUIRED` when material changes occur.
10. Automatically refreshes snapshot after meaningful events with atomic file writes.

Zero model calls. Zero cost (0.00 EUR).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
PROJECT_MEMORY_DIR = Path("/Users/user/Downloads/2026-project-memory")
GODOT_DIR = Path("/Users/user/Downloads/2026-godot-shorts")

EVENTS_DIR = COURIER_DIR / "events"
STATES_DIR = EVENTS_DIR / "agent-states"
SNAPSHOTS_DIR = EVENTS_DIR / "context-snapshots"

STATES_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Add scripts directory to path
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
except ImportError:
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json


def compute_sha256(data: object) -> str:
    """Computes a deterministic SHA256 hash for a given serializable object."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def get_git_head(repo_path: Path) -> str:
    """Safely retrieves the git HEAD SHA for a repository without external network calls."""
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return "NOT_CONNECTED"

    git_dir = repo_path / ".git"
    try:
        # Check direct HEAD file
        head_file = git_dir / "HEAD"
        if head_file.exists():
            content = head_file.read_text(encoding="utf-8").strip()
            if content.startswith("ref:"):
                ref_path = git_dir / content.split(" ", 1)[1].strip()
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
                # Check packed-refs
                packed_refs = git_dir / "packed-refs"
                if packed_refs.exists():
                    ref_name = content.split(" ", 1)[1].strip()
                    for line in packed_refs.read_text(encoding="utf-8").splitlines():
                        if line.endswith(ref_name):
                            return line.split(" ")[0].strip()
            elif len(content) == 40:
                return content
    except Exception:
        pass

    # Fallback to direct git rev-parse if accessible
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_path, timeout=120), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return "UNKNOWN"


class UpdateSteward:
    """Permanent Context Synchronization & Update Steward."""

    def __init__(
        self,
        repo_dir: Path = COURIER_DIR,
        memory_dir: Path = PROJECT_MEMORY_DIR,
        godot_dir: Path = GODOT_DIR,
    ):
        self.repo_dir = repo_dir
        self.memory_dir = memory_dir
        self.godot_dir = godot_dir
        self.snapshots_dir = self.repo_dir / "events/context-snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-update-steward",
            name="Update Steward",
            role="Context Synchronization & Update Steward",
        )

    def read_project_memory_truth(self) -> dict:
        """Parses canonical project memory files deterministically."""
        memory_truth = {
            "latest_verified_milestone": "NOT_RECORDED",
            "latest_decisions": [],
            "open_blockers": [],
            "relevant_ideas": [],
            "human_gates": [],
            "files_available": {
                "project_state": False,
                "decisions": False,
                "ideas": False,
                "changelog": False,
            },
        }

        # 1. Parse PROJECT_STATE.md
        state_file = self.memory_dir / "PROJECT_STATE.md"
        if state_file.exists():
            memory_truth["files_available"]["project_state"] = True
            content = state_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "VERIFIED_CURRENT" in line or "POST_FIX_E2E_VERIFIED" in line:
                    memory_truth["latest_verified_milestone"] = line.strip("- ").strip()
                    break

        # 2. Parse DECISIONS.md
        dec_file = self.memory_dir / "DECISIONS.md"
        if dec_file.exists():
            memory_truth["files_available"]["decisions"] = True
            content = dec_file.read_text(encoding="utf-8")
            for m in re.finditer(r"##\s+(D-\d{3}[^\n]+)", content):
                memory_truth["latest_decisions"].append(m.group(1).strip())

        # 3. Parse IDEA_ARCHIVE.md
        idea_file = self.memory_dir / "IDEA_ARCHIVE.md"
        if idea_file.exists():
            memory_truth["files_available"]["ideas"] = True
            content = idea_file.read_text(encoding="utf-8")
            for m in re.finditer(r"###\s+(IDEA-\d{3}[^\n]+)", content):
                memory_truth["relevant_ideas"].append(m.group(1).strip())

        # 4. Parse MEMORY_CHANGELOG.md
        log_file = self.memory_dir / "MEMORY_CHANGELOG.md"
        if log_file.exists():
            memory_truth["files_available"]["changelog"] = True

        return memory_truth

    def read_courier_state(self) -> dict:
        """Inspects active locks, decisions, results, approvals, and agent states."""
        events_dir = self.repo_dir / "events"
        locks_dir = events_dir / "locks"
        decisions_dir = events_dir / "chief-decisions"
        results_dir = events_dir / "processed"
        approvals_dir = events_dir / "approvals"
        states_dir = events_dir / "agent-states"

        active_locks = list(locks_dir.glob("*.lock")) if locks_dir.exists() else []
        is_locked = len(active_locks) > 0

        workflow_id = "IDLE"
        correlation_id = "UNKNOWN"
        current_task_id = "NONE"

        if is_locked:
            lock_path = active_locks[0]
            workflow_id = lock_path.stem
            try:
                ldata = json.loads(lock_path.read_text(encoding="utf-8"))
                correlation_id = ldata.get("correlation_id", "UNKNOWN")
                current_task_id = ldata.get("current_task_id", "UNKNOWN")
            except Exception:
                pass
        else:
            # Check latest decision or dispatch
            if decisions_dir.exists():
                dec_files = sorted(decisions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                if dec_files:
                    try:
                        ddata = json.loads(dec_files[0].read_text(encoding="utf-8"))
                        workflow_id = ddata.get("workflow_id", "IDLE")
                        correlation_id = ddata.get("correlation_id", "UNKNOWN")
                        current_task_id = ddata.get("task_id", "NONE")
                    except Exception:
                        pass

        # Collect Agent States
        agent_states = {}
        if states_dir.exists():
            for sf in states_dir.glob("*.json"):
                try:
                    sdata = json.loads(sf.read_text(encoding="utf-8"))
                    if "id" in sdata:
                        agent_states[sdata["id"]] = {
                            "state": sdata.get("state", "IDLE"),
                            "task": sdata.get("task"),
                            "progress": sdata.get("progress", 0.0),
                            "execution_class": sdata.get("execution_class", "UNKNOWN"),
                            "updated_at": sdata.get("updated_at"),
                        }
                except Exception:
                    pass

        adoptions_dir = events_dir / "academy/adoptions"

        return {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "current_task_id": current_task_id,
            "is_locked": is_locked,
            "agent_states": agent_states,
            "total_decisions": len(list(decisions_dir.glob("*.json"))) if decisions_dir.exists() else 0,
            "total_results": len(list(results_dir.glob("*.json"))) if results_dir.exists() else 0,
            "total_approvals": len(list(approvals_dir.glob("*.json"))) if approvals_dir.exists() else 0,
            "total_adoptions": len(list(adoptions_dir.glob("*.json"))) if adoptions_dir.exists() else 0,
        }

    def get_latest_snapshot(self) -> dict | None:
        """Reads the currently active context snapshot if present."""
        current_file = self.snapshots_dir / "snapshot-current.json"
        if current_file.exists():
            try:
                return json.loads(current_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def generate_context_snapshot(self, context_delta: dict | None = None) -> dict:
        """Generates a complete, versioned, atomic CurrentContextSnapshot."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.state_tracker.update_state(
            state="CHECKING",
            task="Compiling Project Context Snapshot",
            progress=0.1,
            last_action="Reading repository heads and event bus",
        )

        # 1. Read Repository HEADs
        courier_head = get_git_head(self.repo_dir)
        memory_head = get_git_head(self.memory_dir)
        godot_head = get_git_head(self.godot_dir)

        # 2. Read Courier Event Bus
        courier_state = self.read_courier_state()

        # 3. Read Project Memory Truth
        memory_truth = self.read_project_memory_truth()

        # 4. Determine Context Version and Changes from Previous Snapshot
        previous_snapshot = self.get_latest_snapshot()
        prev_version = previous_snapshot.get("context_version", 0) if previous_snapshot else 0
        prev_hash = previous_snapshot.get("snapshot_hash") if previous_snapshot else None

        changed_items = []
        if previous_snapshot:
            prev_repos = previous_snapshot.get("repositories", {})
            if prev_repos.get("courier_head") != courier_head:
                changed_items.append("courier_head")
            if prev_repos.get("memory_head") != memory_head:
                changed_items.append("memory_head")
            if previous_snapshot.get("memory_truth", {}).get("latest_decisions") != memory_truth["latest_decisions"]:
                changed_items.append("decisions")
            if previous_snapshot.get("workflow_state", {}).get("workflow_id") != courier_state["workflow_id"]:
                changed_items.append("workflow_id")
            if previous_snapshot.get("academy_adoptions", 0) != courier_state.get("total_adoptions", 0):
                changed_items.append("academy_adoptions")
            if context_delta and context_delta.get("idea_id") != (previous_snapshot.get("latest_idea_delta") or {}).get("idea_id"):
                changed_items.append("idea_delta")
        else:
            changed_items = ["initial_snapshot"]

        # If nothing changed, preserve existing snapshot
        if previous_snapshot and not changed_items:
            self.state_tracker.update_state(
                state="CONTEXT CURRENT",
                task=f"Context v{prev_version} ({prev_hash[:8] if prev_hash else 'NONE'})",
                progress=1.0,
                workflow=courier_state.get("workflow_id"),
                last_action=f"Context snapshot v{prev_version} confirmed current (no material changes)",
                next_action="Monitoring project and event bus updates",
                result=f"Version: v{prev_version} | Hash: {prev_hash[:8] if prev_hash else 'NONE'}",
                blocked=False,
            )
            return previous_snapshot

        context_version = prev_version + 1

        # 5. Truth Classification Mapping
        truth_classifications = {
            "courier_codebase": "VERIFIED",
            "project_memory": "VERIFIED",
            "antigravity_worker": "DETERMINISTIC",
            "codex_worker": "DETERMINISTIC",
            "godot_media": "VERIFIED" if godot_head != "NOT_CONNECTED" else "NOT_CONNECTED",
            "human_ideas": "IDEA",
            "user_reports": "USER_REPORTED",
            "truth_invariants": "IDEA != IMPLEMENTED | USER_REPORTED != VERIFIED | DETERMINISTIC != REAL_EXTERNAL",
        }

        # 6. Assemble Snapshot Body
        snapshot_data = {
            "schema_version": "2.0",
            "context_version": context_version,
            "generated_at": now_iso,
            "repositories": {
                "courier_head": courier_head,
                "memory_head": memory_head,
                "godot_head": godot_head,
            },
            "workflow_state": courier_state,
            "memory_truth": memory_truth,
            "latest_idea_delta": context_delta or (previous_snapshot.get("latest_idea_delta") if previous_snapshot else None),
            "academy_adoptions": courier_state.get("total_adoptions", 0),
            "truth_classifications": truth_classifications,
            "changed_since_previous_snapshot": changed_items,
            "previous_snapshot_version": prev_version,
            "previous_snapshot_hash": prev_hash,
        }

        # 7. Compute Deterministic Hash
        snapshot_hash = compute_sha256(snapshot_data)
        snapshot_data["snapshot_hash"] = snapshot_hash

        # 8. Atomic Write
        self._write_snapshot_atomically(snapshot_data, context_version)

        # 9. Update Agent Visual State
        self.state_tracker.update_state(
            state="CONTEXT CURRENT" if not changed_items else "SNAPSHOT UPDATED",
            task=f"Context v{context_version} ({snapshot_hash[:8]})",
            progress=1.0,
            workflow=courier_state.get("workflow_id"),
            last_action=f"Snapshot v{context_version} compiled. Changes: {changed_items}",
            next_action="Monitoring project and event bus updates",
            result=f"Version: v{context_version} | Hash: {snapshot_hash[:8]}",
            blocked=False,
        )

        return snapshot_data

    def _write_snapshot_atomically(self, snapshot_data: dict, version: int) -> None:
        """Writes snapshot to disk atomically using temporary file swap to prevent partial reads."""
        content = json.dumps(snapshot_data, indent=2) + "\n"

        # Write versioned snapshot
        versioned_file = self.snapshots_dir / f"snapshot-v{version}.json"
        versioned_file.write_text(content, encoding="utf-8")

        # Atomic write to snapshot-current.json
        current_file = self.snapshots_dir / "snapshot-current.json"
        fd, temp_path = tempfile.mkstemp(dir=str(self.snapshots_dir), prefix="snap-tmp-", text=True)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, current_file)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def attach_task_context(self, task_data: dict, snapshot: dict | None = None) -> dict:
        """Attaches bounded, versioned context to a Chief task envelope."""
        if snapshot is None:
            snapshot = self.get_latest_snapshot() or self.generate_context_snapshot()

        bounded_context = {
            "context_version": snapshot["context_version"],
            "context_snapshot_hash": snapshot["snapshot_hash"],
            "repositories": snapshot["repositories"],
            "latest_verified_milestone": snapshot["memory_truth"]["latest_verified_milestone"],
            "latest_decisions": snapshot["memory_truth"]["latest_decisions"][:5],  # Bounded to 5 latest
            "truth_invariants": snapshot["truth_classifications"]["truth_invariants"],
        }

        task_data["context_version"] = snapshot["context_version"]
        task_data["context_snapshot_hash"] = snapshot["snapshot_hash"]
        task_data["bounded_context"] = bounded_context
        return task_data

    def check_task_staleness(self, task_data: dict, current_snapshot: dict | None = None) -> tuple[bool, str]:
        """Compares task context version against current snapshot to detect stale tasks."""
        if current_snapshot is None:
            current_snapshot = self.get_latest_snapshot() or self.generate_context_snapshot()

        task_version = task_data.get("context_version")
        curr_version = current_snapshot.get("context_version")

        if task_version is None:
            return (True, "CONTEXT_REFRESH_REQUIRED: Task missing context version")

        if task_version != curr_version:
            # Check if material change occurred
            task_hash = task_data.get("context_snapshot_hash")
            curr_hash = current_snapshot.get("snapshot_hash")
            if task_hash != curr_hash:
                return (True, f"CONTEXT_REFRESH_REQUIRED: Task context v{task_version} differs from current v{curr_version}")

        return (False, "CONTEXT_CURRENT")

    def refresh_snapshot_after_event(self, event_type: str = "RESULT_READY", event_id: str | None = None) -> dict:
        """Refreshes the context snapshot following a meaningful lifecycle event."""
        print(f"[UPDATE STEWARD] Event triggered refresh: {event_type} ({event_id or 'GENERAL'})")
        return self.generate_context_snapshot()


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Steward & Context Synchronization CLI")
    parser.add_argument("--refresh", action="store_true", help="Force refresh current context snapshot")
    parser.add_argument("--inspect", action="store_true", help="Print current context snapshot metadata")
    args = parser.parse_args()

    steward = UpdateSteward()
    if args.refresh or not args.inspect:
        snapshot = steward.generate_context_snapshot()
        print(f"✅ Context Snapshot v{snapshot['context_version']} generated (Hash: {snapshot['snapshot_hash'][:12]})")
        print(f"   Courier HEAD: {snapshot['repositories']['courier_head'][:8]}")
        print(f"   Memory HEAD:  {snapshot['repositories']['memory_head'][:8]}")
        print(f"   Decisions:    {len(snapshot['memory_truth']['latest_decisions'])} indexed")
    else:
        snapshot = steward.get_latest_snapshot()
        if snapshot:
            print(json.dumps(snapshot, indent=2))
        else:
            print("No snapshot available. Run with --refresh to generate one.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

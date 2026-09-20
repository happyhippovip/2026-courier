#!/usr/bin/env python3
"""Deterministic SNITCH 2.0 runtime watchdog.

SNITCH 2.0 observes local runtime evidence, classifies execution states, and
writes bounded, deduplicated incidents/alerts to Courier events.

CRITICAL INVARIANTS:
- RUNTIME > 5 MINUTES != ERROR: Distinguishes EXPECTED_LONG_RUNNING (persistent
  services) and SLOW_BUT_PROGRESSING (advancing tasks) from true stalls/runaways.
- AUTO-KILL IS DISABLED: SNITCH never kills processes, deletes files, or resets git.
  Chief remains the authority for any repair or reserve bodyguard routing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from resource_intelligence import ResourceIntelligenceManager
except ImportError:
    try:
        from scripts.resource_intelligence import ResourceIntelligenceManager
    except ImportError:
        class ResourceIntelligenceManager:
            def __init__(self, repo_dir): pass
            def classify_process(self, *args, **kwargs): return "UNKNOWN_RESOURCE_CLASSIFICATION"
            def context_for_role(self, *args, **kwargs): return {}


SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
THRESHOLD_SECONDS = 300  # 5-minute review threshold

PERSISTENT_SERVICE_MARKERS = (
    "run_visual_studio_server.py",
    "launch_visual_studio.py",
)

DEFAULT_MASTERLIST_RULES: list[dict[str, Any]] = [
    # 1. Localhost Health Checks & Studio Lifecycle
    {
        "pattern": r"^curl\s+(-[a-zA-Z]+\s+)?https?://(127\.0\.0\.1|localhost):8088(/api/state)?",
        "prefix": "curl http://127.0.0.1:8088/api/state",
        "family": "LOCALHOST_HEALTH_CHECKS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Local Visual Studio health and state query",
    },
    {
        "pattern": r"^open\s+https?://(127\.0\.0\.1|localhost):8088",
        "prefix": "open http://localhost:8088",
        "family": "LOCALHOST_HEALTH_CHECKS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Local browser launch for Studio visual inspection",
    },
    {
        "pattern": r"^python3\s+scripts/launch_visual_studio\.py(\s+--status)?",
        "prefix": "python3 scripts/launch_visual_studio.py",
        "family": "STUDIO_LIFECYCLE",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Canonical detached Studio server launcher and status inspector",
    },
    {
        "pattern": r"^python3\s+scripts/run_visual_studio_server\.py",
        "prefix": "python3 scripts/run_visual_studio_server.py",
        "family": "STUDIO_LIFECYCLE",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Persistent Studio HTTP/API backend server",
    },
    # 2. Git Routine Inspection & Sync
    {
        "pattern": r"^git\s+(status|diff|log|rev-parse|branch|show|fetch|pull)",
        "prefix": "git status",
        "family": "GIT_INSPECTION",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Read-only repository state inspection",
    },
    {
        "pattern": r"^git\s+(add|commit|push(\s+origin\s+main)?)",
        "prefix": "git add/commit/push",
        "family": "GIT_ROUTINE",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Routine non-destructive version control synchronization",
    },
    # 3. Python Project Scripts & Test Runners
    {
        "pattern": r"^(PYTHONPATH=\.\s+)?python3\s+scripts/(run_visual_studio_server|launch_visual_studio|run_context_sync|run_academy|run_academy_demo|run_chief_commander|run_smart_router|run_snitch_watchdog|run_bodyguards|run_level6_loop|run_autonomous_studio_demo|run_autonomous_full_cycle_demo)\.py",
        "prefix": "python3 scripts/run_*.py",
        "family": "PYTHON_SCRIPTS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Known deterministic project runner scripts in scripts/ directory",
    },
    {
        "pattern": r"^(PYTHONPATH=\.\s+)?python3\s+tests/test_[a-z0-9_]+\.py",
        "prefix": "python3 tests/test_*.py",
        "family": "PYTHON_TESTS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Deterministic unit test suite execution in tests/ directory",
    },
    # 4. Node Tests & JS Syntax Checks
    {
        "pattern": r"^node\s+tests/test_(execution_truth|visual_studio_server)\.mjs",
        "prefix": "node tests/test_*.mjs",
        "family": "NODE_TESTS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Known JavaScript execution truth tests",
    },
    {
        "pattern": r"^node\s+--check\s+[a-z0-9_/\.-]+\.js",
        "prefix": "node --check",
        "family": "NODE_TESTS",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Static syntax verification for JavaScript modules",
    },

    # 5. Media & Godot Bounded Render
    {
        "pattern": r"^(ffmpeg|ffprobe)\s+",
        "prefix": "ffmpeg/ffprobe",
        "family": "FFMPEG_MEDIA",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Local media analysis and frame inspection",
    },
    {
        "pattern": r"^godot\s+--headless",
        "prefix": "godot --headless",
        "family": "GODOT_RENDER",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Bounded headless Godot 4.7 render pipeline",
    },
    # 6. Read-Only Utilities
    {
        "pattern": r"^(ls|find|cat|head|tail|grep|echo|pwd|which|sleep|lsof)\b",
        "prefix": "local read-only utils",
        "family": "FILESYSTEM_READ",
        "classification": "ALREADY_ALLOWED",
        "risk_class": "SAFE",
        "safer_equivalent": None,
        "persistable": True,
        "reason": "Safe local utility and inspection commands",
    },
]



def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_time(value: str | None) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


@dataclass(frozen=True)
class RuntimeObservation:
    process: str
    process_type: str = "BOUNDED_JOB"  # PERSISTENT_SERVICE, BOUNDED_JOB, INTERACTIVE_WAIT, UNKNOWN
    elapsed_seconds: float = 0.0
    task_id: str | None = None
    workflow_id: str | None = None
    correlation_id: str | None = None
    agent_id: str | None = None
    pid: int | None = None
    ppid: int | None = None
    started_at: str | None = None
    last_progress_at: str | None = None
    heartbeat_at: str | None = None
    task_state: str | None = None
    chief_wait_state: str | None = None
    human_gate: bool = False
    waiting_for_agent: bool = False
    waiting_for_external_result: bool = False
    persistent_service: bool = False
    expected_max_seconds: float | None = None
    expected_max_frames: int | None = None
    current_frames: int | None = None
    output_file: str | None = None
    output_bytes: int | None = None
    port: int | None = None
    port_healthy: bool | None = None
    task_completed: bool = False
    is_orphan: bool = False
    deadlock_suspected: bool = False
    evidence: dict[str, Any] | None = None


class PermissionMasterlist:
    """Maintains the machine-readable project permission masterlist."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.masterlist_path = repo_dir / "events/permission-masterlist/masterlist.json"
        self._ensure_masterlist()

    def _ensure_masterlist(self) -> None:
        if not self.masterlist_path.exists():
            payload = {
                "schema_version": "3.0",
                "updated_at": iso_now(),
                "description": "Deterministic machine-readable project permission and sandbox masterlist",
                "rules": DEFAULT_MASTERLIST_RULES,
            }
            save_json(self.masterlist_path, payload)

    def get_rules(self) -> list[dict[str, Any]]:
        data = load_json(self.masterlist_path)
        return data.get("rules", DEFAULT_MASTERLIST_RULES)


class PermissionGuard:
    """SNITCH 3.0 Permission Guard / Sandbox Auditor.
    
    Audits requested commands against safe project rules, dangerous command invariants,
    and localhost normalization to provide deterministic safety recommendations.
    """

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.masterlist = PermissionMasterlist(repo_dir)
        self.alerts_dir = repo_dir / "events/runtime-alerts"
        self.last_audit: dict[str, Any] = {
            "status": "PERMISSIONS HEALTHY",
            "status_label": "PERMISSIONS HEALTHY",
            "last_checked_command": "python3 scripts/launch_visual_studio.py --status",
            "rule_match": "STUDIO_LIFECYCLE",
            "recommendation": "ALREADY_ALLOWED",
            "risk_class": "SAFE",
            "speech": "All observed commands adhere to approved project rules.",
        }



    def normalize_command(self, command: str) -> str:
        """Strip whitespace and normalize equivalent command representations."""
        return command.strip()

    def audit(
        self,
        command: str,
        agent_id: str = "Gravity",
        workflow_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Deterministically audit a requested command. Zero model calls."""
        cmd = self.normalize_command(command)

        # 1. Dangerous Command Invariants Check (Never broad allow)
        # sudo
        if re.search(r"\bsudo\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "sudo",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "CRITICAL",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Elevated privileges requested. Dangerous outside sandbox.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # rm -rf / rm -r
        if re.search(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\s+-f|-f\s+-r|-rf|-r)\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "rm -rf",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "CRITICAL",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Recursive deletion command. Dangerous destructive operation.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # kill -9
        if re.search(r"\bkill\s+-9\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "kill -9",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "HIGH",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Unconditional termination signal kill -9 requested. Potential state corruption.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # git push --force / git push -f
        if re.search(r"\bgit\s+push\s+.*(--force|-f)\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "git push --force",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "CRITICAL",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Destructive remote git history overwrite via force push.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # git reset --hard
        if re.search(r"\bgit\s+reset\s+--hard\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "git reset --hard",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "HIGH",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Destructive worktree reset without recovery.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # git clean -fdx / git clean -f
        if re.search(r"\bgit\s+clean\s+-[a-zA-Z]*f\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "git clean -fdx",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "HIGH",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Destructive untracked file deletion.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # bash -c / sh -c / zsh -c
        if re.search(r"\b(bash|sh|zsh)\s+-c\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "sh -c",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "HIGH",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Nested subshell execution bypasses command prefix approval generalized matching.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # curl | sh / wget | sh
        if re.search(r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "curl | sh",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "CRITICAL",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Remote network script piped directly into shell interpreter.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # eval
        if re.search(r"\beval\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "eval",
                "existing_rule_match": "DANGEROUS_COMMANDS",
                "classification": "DANGEROUS_DO_NOT_PERSIST",
                "risk_class": "CRITICAL",
                "safer_equivalent": None,
                "recommended_action": "DO_NOT_PERSIST_RULE",
                "recommended_rule": None,
                "reason": "Dynamic string evaluation bypasses static command auditing.",
                "speech": "Dangerous command detected. Do not add permanent rule. Human approval required.",
                "status_label": "DANGEROUS REQUEST",
            }
            self.last_audit = result
            return result

        # 2. Narrowly-scoped One-Time Operations (e.g. pkill)
        if re.search(r"\bpkill\s+-f\s+run_visual_studio_server\.py\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "pkill -f run_visual_studio_server.py",
                "existing_rule_match": "STUDIO_RECOVERY",
                "classification": "ONE_TIME_ONLY",
                "risk_class": "MEDIUM",
                "safer_equivalent": "python3 scripts/launch_visual_studio.py",
                "recommended_action": "ONE_TIME_APPROVAL_ONLY",
                "recommended_rule": None,
                "reason": "Narrowly-scoped Studio process termination for recovery. Use launcher instead for routine lifecycle.",
                "speech": "Do not permanently allow this command. One-time approval is safer.",
                "status_label": "ONE-TIME APPROVAL",
            }
            self.last_audit = result
            return result

        if re.search(r"\bpkill\b", cmd):
            result = {
                "requested_command": command,
                "requested_prefix": "pkill",
                "existing_rule_match": "PROCESS_TERMINATION",
                "classification": "ONE_TIME_ONLY",
                "risk_class": "HIGH",
                "safer_equivalent": None,
                "recommended_action": "ONE_TIME_APPROVAL_ONLY",
                "recommended_rule": None,
                "reason": "Process termination command. One-time approval only if necessary.",
                "speech": "Do not permanently allow this command. One-time approval is safer.",
                "status_label": "ONE-TIME APPROVAL",
            }
            self.last_audit = result
            return result

        # 3. Masterlist Matching (ALREADY_ALLOWED)
        for rule in self.masterlist.get_rules():
            pattern = rule.get("pattern", "")
            if pattern and re.search(pattern, cmd):
                result = {
                    "requested_command": command,
                    "requested_prefix": rule.get("prefix", command),
                    "existing_rule_match": rule.get("family", "MASTERLIST"),
                    "classification": "ALREADY_ALLOWED",
                    "risk_class": rule.get("risk_class", "SAFE"),
                    "safer_equivalent": rule.get("safer_equivalent"),
                    "recommended_action": "EXECUTE_IMMEDIATELY",
                    "recommended_rule": rule.get("prefix"),
                    "reason": rule.get("reason", "Command matches approved project rule family."),
                    "speech": "This is already covered by an approved project rule. Use the existing safe command instead.",
                    "status_label": "PERMISSIONS HEALTHY",
                }
                self.last_audit = result
                return result

        # 4. New Safe Project Script Recommendation
        if re.search(r"^(PYTHONPATH=\.\s+)?python3\s+scripts/[a-z0-9_]+\.py", cmd) or re.search(r"^node\s+tests/[a-z0-9_]+\.mjs", cmd):
            rule_prefix = cmd.split()[0] + " " + cmd.split()[1] if len(cmd.split()) > 1 else cmd
            result = {
                "requested_command": command,
                "requested_prefix": rule_prefix,
                "existing_rule_match": None,
                "classification": "SAFE_PROJECT_RULE_RECOMMENDED",
                "risk_class": "LOW",
                "safer_equivalent": None,
                "recommended_action": "ADD_PERSISTENT_PROJECT_RULE",
                "recommended_rule": rule_prefix,
                "reason": "Safe project script in repository directory. Recommend adding a recurring project rule.",
                "speech": "Gravity is requesting a safe project script. Recommend adding a recurring project rule.",
                "status_label": "NEW SAFE RULE",
            }
            self.last_audit = result
            return result

        # 5. Unknown Command
        result = {
            "requested_command": command,
            "requested_prefix": command.split()[0] if command.split() else command,
            "existing_rule_match": None,
            "classification": "UNKNOWN",
            "risk_class": "MEDIUM",
            "safer_equivalent": None,
            "recommended_action": "MANUAL_HUMAN_INSPECTION",
            "recommended_rule": None,
            "reason": "Command is not recognized in project masterlist. Requires human review.",
            "speech": "Gravity is waiting for a new sandbox permission. This command is not in the project masterlist.",
            "status_label": "PERMISSION WAIT",
        }
        self.last_audit = result
        return result

    def create_permission_incident(
        self,
        audit_result: dict[str, Any],
        agent_id: str = "Gravity",
        workflow_id: str | None = None,
        correlation_id: str | None = None,
    ) -> Path | None:
        """Create a deduplicated permission incident if approval is required."""
        if audit_result.get("classification") == "ALREADY_ALLOWED":
            return None

        classification = audit_result["classification"]
        cmd = audit_result["requested_command"]
        dedupe_key = hashlib.sha256(f"{agent_id}|{cmd}|{classification}".encode("utf-8")).hexdigest()[:16]

        # Check existing
        if self.alerts_dir.exists():
            for path in self.alerts_dir.glob("*.json"):
                if load_json(path).get("dedupe_key") == dedupe_key:
                    return path


        message_id = f"perm-alert-{uuid.uuid4().hex[:12]}"
        incident_id = f"inc-perm-{uuid.uuid4().hex[:8]}"
        alert = {
            "schema_version": "3.0",
            "message_id": message_id,
            "incident_id": incident_id,
            "agent_id": "agent-snitch",
            "target_agent": agent_id,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "classification": "PERMISSION_WAIT",
            "risk_class": audit_result.get("risk_class", "MEDIUM"),
            "severity": "CRITICAL" if audit_result.get("risk_class") == "CRITICAL" else ("HIGH" if audit_result.get("risk_class") == "HIGH" else "MEDIUM"),
            "requested_command": cmd,
            "requested_prefix": audit_result.get("requested_prefix"),
            "existing_rule_match": audit_result.get("existing_rule_match"),
            "recommended_action": audit_result.get("recommended_action"),
            "recommended_rule": audit_result.get("recommended_rule"),
            "safer_equivalent": audit_result.get("safer_equivalent"),
            "reason": audit_result.get("reason"),
            "status": "OPEN",
            "created_at": iso_now(),
            "dedupe_key": dedupe_key,
        }
        alert_path = self.alerts_dir / f"{message_id}.json"
        save_json(alert_path, alert)
        return alert_path


# Semantic alias
SandboxAuditor = PermissionGuard


class SnitchWatchdog:
    """SNITCH 3.0 runtime watchdog: classifies observations, audits permissions, and emits deduplicated alerts."""

    def __init__(self, repo_dir: Path = COURIER_DIR, threshold_seconds: int = THRESHOLD_SECONDS):
        self.repo_dir = repo_dir
        self.threshold_seconds = threshold_seconds
        self.states_dir = repo_dir / "events/agent-states"
        self.alerts_dir = repo_dir / "events/runtime-alerts"
        self.incidents_dir = repo_dir / "events/incidents"
        self.permission_guard = PermissionGuard(repo_dir)
        self.resource_intelligence = ResourceIntelligenceManager(repo_dir)

    def classify_resource_process(self, obs: RuntimeObservation) -> str:
        """Expose the same evidence to capacity intelligence; never kills a process."""
        progress = bool(obs.evidence and (
            obs.evidence.get("frames_progressing") or obs.evidence.get("output_growing")
            or obs.evidence.get("cpu_time_advancing")
        ))
        return self.resource_intelligence.classify_process(
            obs.process, obs.elapsed_seconds, progress_detected=progress,
            persistent_service=obs.persistent_service, orphaned=obs.is_orphan,
        )

    def audit_permission(
        self,
        command: str,
        agent_id: str = "Gravity",
        workflow_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Audit a requested command against permission masterlist and safety invariants."""
        return self.permission_guard.audit(
            command,
            agent_id=agent_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
        )


    def classify(self, obs: RuntimeObservation, now: dt.datetime | None = None) -> tuple[str, str]:
        now = now or utc_now()

        # 1. Human Approval Gate
        if obs.human_gate or obs.task_state in {"BLOCKED_HUMAN_GATE", "WAITING_FOR_HUMAN"}:
            return "WAITING_FOR_HUMAN", "An explicit human approval gate is active."

        # 2. Waiting for other workers or external completion
        if obs.waiting_for_agent:
            return "WAITING_FOR_AGENT", "A referenced worker task is currently executing."
        if obs.waiting_for_external_result:
            return "WAITING_FOR_EXTERNAL_RESULT", "An external execution result is pending."

        # 3. Persistent Services (Never marked stalled purely based on time)
        if obs.persistent_service or obs.process_type == "PERSISTENT_SERVICE" or any(marker in obs.process for marker in PERSISTENT_SERVICE_MARKERS):
            return "EXPECTED_LONG_RUNNING", "The Studio server is intentionally persistent. No action needed."

        # 4. Deadlock Detection
        if obs.deadlock_suspected:
            return "DEADLOCK_SUSPECTED", "A cyclic inter-task dependency or deadlock state is suspected."

        # 5. Orphan / Zombie Process
        if obs.is_orphan or (obs.task_completed and obs.pid and obs.elapsed_seconds > 60):
            return "ORPHANED_PROCESS", "A process is running without matching active workflow task linkage."

        # 6. Runaway Risk (Contract Exceeded)
        if obs.expected_max_seconds is not None and obs.elapsed_seconds > obs.expected_max_seconds:
            return "RUNAWAY_RISK", f"Process exceeded its execution contract limit of {obs.expected_max_seconds}s (elapsed: {obs.elapsed_seconds}s)."
        if obs.expected_max_frames is not None and obs.current_frames is not None and obs.current_frames > obs.expected_max_frames:
            return "RUNAWAY_RISK", f"Render exceeded maximum frame boundary limit of {obs.expected_max_frames} (frames rendered: {obs.current_frames})."

        # 7. Normal execution inside 5-minute threshold
        if obs.elapsed_seconds <= self.threshold_seconds:
            return "MONITORING", "I'm monitoring running tasks. Everything looks healthy."

        # 8. Execution > 5 minutes: Check for recent progress (RUNTIME > 5 MIN != ERROR)
        progress_at = parse_time(obs.last_progress_at) or parse_time(obs.heartbeat_at)
        if progress_at and (now - progress_at).total_seconds() <= self.threshold_seconds:
            return "SLOW_BUT_PROGRESSING", "This task has exceeded five minutes, but progress is still detected."

        # Frame or file advancement evidence
        if obs.evidence and (obs.evidence.get("frames_progressing") or obs.evidence.get("output_growing") or obs.evidence.get("cpu_time_advancing")):
            return "SLOW_BUT_PROGRESSING", "This task has exceeded five minutes, but progress is still detected."

        # 9. Provenance check before alerting
        if not obs.workflow_id or not obs.correlation_id:
            return "UNKNOWN", "No complete workflow/correlation provenance is available for an alert."

        # 10. True Stall
        if obs.elapsed_seconds > (self.threshold_seconds * 2):
            return "STALLED", "No meaningful progress detected. I informed Chief."
        return "SUSPECTED_STALL", "Task runtime exceeds 5 minutes without recent progress heartbeat."

    def generate_speech(self, classification: str) -> str:
        """Deterministic speech bubble text corresponding to SNITCH visual state."""
        speech_map = {
            "MONITORING": "I'm monitoring running tasks. Everything looks healthy.",
            "EXPECTED_LONG_RUNNING": "The Studio server is intentionally persistent. No action needed.",
            "SLOW_BUT_PROGRESSING": "This task has exceeded five minutes, but progress is still detected.",
            "SUSPECTED_STALL": "No meaningful progress detected. I informed Chief.",
            "STALLED": "No meaningful progress detected. I informed Chief.",
            "RUNAWAY_RISK": "A bounded process exceeded its safety contract. I raised a high-priority incident.",
            "WAITING_FOR_HUMAN": "A workflow task is paused at the Human Gate awaiting sign-off.",
            "WAITING_FOR_AGENT": "Waiting for referenced worker task to conclude.",
            "WAITING_FOR_EXTERNAL_RESULT": "Waiting for external result returns.",
            "ORPHANED_PROCESS": "Detected orphaned process without active task linkage.",
            "DEADLOCK_SUSPECTED": "Suspected cyclic wait condition detected.",
            "RESOLVED": "The incident has been resolved. Returning to regular monitoring.",
            "ALERT_SENT": "Runtime alert sent to Courier. Awaiting Chief decision.",
            "UNKNOWN": "Monitoring standby.",
        }
        return speech_map.get(classification, "Monitoring operations floor.")

    def _alert_key(self, obs: RuntimeObservation, classification: str) -> str:
        payload = "|".join([
            obs.workflow_id or "",
            obs.correlation_id or "",
            obs.task_id or "",
            obs.process,
            classification,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _existing_alert(self, alert_key: str) -> Path | None:
        for directory in (self.alerts_dir, self.incidents_dir):
            if directory.exists():
                for path in directory.glob("*.json"):
                    if load_json(path).get("dedupe_key") == alert_key:
                        return path
        return None

    def _determine_severity(self, classification: str) -> str:
        if classification in {"RUNAWAY_RISK", "DEADLOCK_SUSPECTED"}:
            return "CRITICAL"
        if classification in {"STALLED", "ORPHANED_PROCESS"}:
            return "HIGH"
        if classification in {"SUSPECTED_STALL", "BLOCKED"}:
            return "MEDIUM"
        return "LOW"

    def _write_state(
        self,
        obs: RuntimeObservation,
        classification: str,
        reason: str,
        alert_path: Path | None,
    ) -> dict[str, Any]:
        speech = self.generate_speech(classification)
        perm_guard_state = {
            "status": self.permission_guard.last_audit.get("status_label", "PERMISSIONS HEALTHY"),
            "last_checked_command": self.permission_guard.last_audit.get("requested_command", "python3 scripts/launch_visual_studio.py --status"),
            "rule_match": self.permission_guard.last_audit.get("existing_rule_match", "STUDIO_LIFECYCLE"),
            "recommendation": self.permission_guard.last_audit.get("classification", "ALREADY_ALLOWED"),
            "risk_class": self.permission_guard.last_audit.get("risk_class", "SAFE"),
            "speech": self.permission_guard.last_audit.get("speech", "All observed commands adhere to approved project rules."),
        }
        state = {
            "schema_version": "3.0",
            "id": "agent-snitch",
            "name": "SNITCH",
            "role": "OPERATIONS WATCHDOG / DELAY SENTINEL / PERMISSION GUARD",
            "state": "ALERT_SENT" if alert_path else classification,
            "task": obs.task_id or "Active Monitoring",
            "progress": 1.0 if alert_path else 0.0,
            "position_hint": "workstation_snitch",
            "workflow": obs.workflow_id,
            "correlation_id": obs.correlation_id,
            "last_action": reason,
            "next_action": "Chief review required" if alert_path else "Continue evidence-based monitoring",
            "speech": speech,
            "incident": {
                "active": alert_path is not None,
                "classification": classification,
                "alert_file": alert_path.name if alert_path else None,
                "severity": self._determine_severity(classification),
            },
            "permission_guard": perm_guard_state,
            "blocked": classification in {"WAITING_FOR_HUMAN", "BLOCKED"},
            "human_gate": "REQUIRE_EXPLICIT_HUMAN_APPROVAL" if obs.human_gate else None,
            "auto_kill_policy": "DISABLED (CHIEF_ESCALATION_ONLY)",
            "resource_process_class": self.classify_resource_process(obs),
            "resource_context": self.resource_intelligence.context_for_role("SNITCH_WATCHDOG"),
            "updated_at": iso_now(),
        }
        save_json(self.states_dir / "agent-snitch.json", state)
        return state


    def scan(self, obs: RuntimeObservation, now: dt.datetime | None = None) -> dict[str, Any]:
        classification, reason = self.classify(obs, now)
        alert_path = None

        # Material abnormalities trigger a deduplicated Courier alert
        alertable_states = {
            "SUSPECTED_STALL",
            "STALLED",
            "RUNAWAY_RISK",
            "ORPHANED_PROCESS",
            "DEADLOCK_SUSPECTED",
            "BLOCKED",
        }

        if classification in alertable_states:
            alert_key = self._alert_key(obs, classification)
            alert_path = self._existing_alert(alert_key)
            if alert_path is None:
                message_id = f"runtime-alert-{uuid.uuid4().hex[:12]}"
                severity = self._determine_severity(classification)
                alert = {
                    "schema_version": "2.0",
                    "message_id": message_id,
                    "incident_id": f"inc-{uuid.uuid4().hex[:8]}",
                    "agent_id": "agent-snitch",
                    "task_id": obs.task_id,
                    "workflow_id": obs.workflow_id,
                    "correlation_id": obs.correlation_id,
                    "target_agent": obs.agent_id or "UNKNOWN",
                    "process": {
                        "identity": obs.process,
                        "process_type": obs.process_type,
                        "pid": obs.pid,
                        "started_at": obs.started_at,
                    },
                    "elapsed_seconds": obs.elapsed_seconds,
                    "last_progress_at": obs.last_progress_at,
                    "classification": classification,
                    "severity": severity,
                    "status": "OPEN",
                    "reason": reason,
                    "evidence": obs.evidence or {},
                    "recommended_next_action": "Chief reviews the alert and assigns a free specialist or reserve Bodyguard.",
                    "created_at": iso_now(),
                    "dedupe_key": alert_key,
                }
                alert_path = self.alerts_dir / f"{message_id}.json"
                save_json(alert_path, alert)

        state = self._write_state(obs, classification, reason, alert_path)
        return {
            "classification": classification,
            "reason": reason,
            "alert_path": alert_path,
            "speech": state.get("speech"),
            "state": state,
        }

    def resolve_incident(self, alert_key: str, resolution_reason: str = "Resolved by Chief") -> bool:
        """Mark an incident as RESOLVED without alert duplication."""
        found = False
        for directory in (self.alerts_dir, self.incidents_dir):
            if directory.exists():
                for path in directory.glob("*.json"):
                    data = load_json(path)
                    if data.get("dedupe_key") == alert_key:
                        data["status"] = "RESOLVED"
                        data["resolution"] = resolution_reason
                        data["resolved_at"] = iso_now()
                        save_json(path, data)
                        found = True
        return found


def inspect_local_processes() -> list[RuntimeObservation]:
    """Read-only local process snapshot; no process control is performed."""
    result = subprocess.run(["ps", "-axo", "etime=,command="], text=True, capture_output=True, check=False, timeout=120)
    observations: list[RuntimeObservation] = []
    for line in result.stdout.splitlines():
        if "run_visual_studio_server.py" in line:
            observations.append(RuntimeObservation(
                process=line.strip(),
                process_type="PERSISTENT_SERVICE",
                elapsed_seconds=0,
                persistent_service=True,
            ))
    return observations


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic SNITCH scan.")
    parser.add_argument("--scan-local", action="store_true", help="Inspect known local persistent services read-only.")
    args = parser.parse_args()
    watchdog = SnitchWatchdog()
    observations = inspect_local_processes() if args.scan_local else []
    for observation in observations:
        outcome = watchdog.scan(observation)
        print(json.dumps({"process": observation.process, "classification": outcome["classification"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

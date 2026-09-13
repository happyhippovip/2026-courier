#!/usr/bin/env python3
"""Computer-A Autonomy: Useful-Work Selection & False-Ready Defense Engine.

Implements grounded, deterministic, zero-spend useful-work discovery, classification,
false-ready defense, priority scoring, and state machine lifecycle management for Computer A:
- 100% Deterministic (0 Model Calls, 0 EUR Spend)
- 12-State Authoritative Opportunity Classifier
- Strict False-Ready Defense (No task is READY merely because an old queue file says so)
- Anti-Semantic-Duplicate Defense using Canonical Cryptographic Fingerprints
- 8-Tier Grounded Local Discovery when explicit queues are empty
- Hard Gate Enforcement overriding numerical scores (Money, Human, Publication, Boundaries)
- Authoritative State Lifecycle (QUEUE_EMPTY, TASK_SUCCESS, TASK_FAILURE, TASK_HUNG, etc.)
- Rejection of synthetic filler, paused creator/video tasks, Computer B, and universuX.
"""

from __future__ import annotations

import ast
import datetime as dt
import enum
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class WorkReadinessState(str, enum.Enum):
    READY_HIGH_VALUE = "READY_HIGH_VALUE"
    READY_USEFUL = "READY_USEFUL"
    NEUTRAL = "NEUTRAL"
    COMPLETED = "COMPLETED"
    DUPLICATE = "DUPLICATE"
    STALE = "STALE"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    HUMAN_GATE = "HUMAN_GATE"
    MONEY_GATE = "MONEY_GATE"
    PUBLICATION_GATE = "PUBLICATION_GATE"
    PROTECTED_BOUNDARY_GATED = "PROTECTED_BOUNDARY_GATED"
    NO_INFORMATION_GAIN = "NO_INFORMATION_GAIN"
    UNKNOWN = "UNKNOWN"


class AutonomyLifecycleState(str, enum.Enum):
    QUEUE_EMPTY = "QUEUE_EMPTY"
    TASK_RUNNING = "TASK_RUNNING"
    TASK_SUCCESS = "TASK_SUCCESS"
    TASK_FAILURE = "TASK_FAILURE"
    TASK_HUNG = "TASK_HUNG"
    TASK_BLOCKED = "TASK_BLOCKED"
    HUMAN_GATE = "HUMAN_GATE"
    RESOURCE_LOW = "RESOURCE_LOW"
    RESTART = "RESTART"
    STOP = "STOP"
    RESUME = "RESUME"
    SAFE_IDLE = "SAFE_IDLE"


PROTECTED_PROJECT_NAMES = {
    "universux",
    "universuX",
    "node_b",
    "computer_b",
    "computer-b",
    "node-b",
    "creator_video_rendering",
    "creator_video_renderer",
    "video_production",
    "tiktok_publish",
    "youtube_publish",
}

BUSYWORK_KEYWORDS = {
    "cosmetic refactor",
    "format unchanged",
    "re-analyze unchanged",
    "duplicate documentation",
    "quota consumption",
    "filler loop",
    "synthetic status report",
    "repeated summary",
}


def compute_canonical_work_fingerprint(
    objective: str,
    scope: List[str],
    task_type: str,
    evidence_hash: str = "",
) -> str:
    """Computes a semantic-invariant canonical fingerprint preventing duplicate tasks."""
    # Normalize objective text: lowercase, remove punctuation, strip extra whitespace
    norm_obj = re.sub(r"[^\w\s]", "", objective.lower()).strip()
    norm_obj = " ".join(norm_obj.split())
    norm_scope = ",".join(sorted(s.strip().rstrip("/").lower() for s in scope if s.strip()))
    norm_type = task_type.strip().upper()
    raw = f"{norm_obj}|{norm_scope}|{norm_type}|{evidence_hash.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass
class ScoredCandidateTask:
    task_id: str
    objective: str
    readiness_state: WorkReadinessState
    task_type: str = "SAFE_LOCAL_ENGINEERING"
    scope: List[str] = field(default_factory=list)
    project: str = "2026-courier"
    value_score: float = 5.0
    information_gain: float = 5.0
    risk_score: float = 1.0
    dependency_readiness: float = 10.0
    resource_cost: float = 0.0
    recency_score: float = 8.0
    duplicate_probability: float = 0.0
    time_to_verify_seconds: float = 5.0
    final_score: float = 0.0
    is_actionable: bool = False
    gate_reason: Optional[str] = None
    fingerprint: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["readiness_state"] = self.readiness_state.value
        return d


class UsefulWorkSelectionEngine:
    """Authoritative decision and ranking engine for autonomous Computer A tasks."""

    HEAVY_JOB_LIMIT = 1

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.events_dir = self.repo_dir / "events"
        self.state_dir = self.events_dir / "runtime-state"
        self.completed_ledger = self.events_dir / "opportunity-queue" / "historical_ledger.json"
        self.completed_fps_file = self.events_dir / "autonomy-dispatcher" / "completed_task_fingerprints.json"
        self.circuit_breakers_dir = self.events_dir / "circuit-breakers"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.circuit_breakers_dir.mkdir(parents=True, exist_ok=True)

        self._completed_fingerprints: Set[str] = set()
        self._load_completed_fingerprints()

    def _load_completed_fingerprints(self) -> None:
        """Loads completed task fingerprints from historical ledgers."""
        if self.completed_fps_file.is_file():
            try:
                data = json.loads(self.completed_fps_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._completed_fingerprints.update(data)
            except Exception:
                pass

        if self.completed_ledger.is_file():
            try:
                data = json.loads(self.completed_ledger.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        fp = item.get("completion_fingerprint") or item.get("task_fingerprint")
                        if fp:
                            self._completed_fingerprints.add(fp)
            except Exception:
                pass

    def record_completed_fingerprint(self, fingerprint: str) -> None:
        self._completed_fingerprints.add(fingerprint)
        self.completed_fps_file.parent.mkdir(parents=True, exist_ok=True)
        self.completed_fps_file.write_text(
            json.dumps(sorted(list(self._completed_fingerprints)), indent=2) + "\n",
            encoding="utf-8"
        )

    def is_fingerprint_completed(self, fingerprint: str) -> bool:
        return fingerprint in self._completed_fingerprints

    # =========================================================================
    # PHASE B: FALSE-READY DEFENSE & CLASSIFICATION
    # =========================================================================
    def classify_opportunity(self, opp_dict: Dict[str, Any]) -> Tuple[WorkReadinessState, Optional[str]]:
        """Authoritatively classifies any opportunity candidate into a distinct readiness state."""
        opp_id = str(opp_dict.get("opportunity_id", ""))
        obj = str(opp_dict.get("objective", opp_dict.get("description", "")))
        project = str(opp_dict.get("project", "")).lower()
        task_type = str(opp_dict.get("task_type", opp_dict.get("source", ""))).upper()
        raw_status = str(opp_dict.get("status", "READY")).upper()
        scope = list(opp_dict.get("allowed_scope", opp_dict.get("scope", [])))
        cost = float(opp_dict.get("estimated_cost", 0.0))
        requires_payment = bool(opp_dict.get("requires_payment", False)) or cost > 0.0
        requires_human = bool(opp_dict.get("requires_human", False))
        evidence = dict(opp_dict.get("evidence", {}))

        # 1. Protected Boundary Gate (Computer B, universuX, paused creator video rendering)
        if any(p in project or p in obj.lower() or p in task_type.lower() for p in PROTECTED_PROJECT_NAMES):
            return WorkReadinessState.PROTECTED_BOUNDARY_GATED, "PROTECTED_PROJECT_OR_PAUSED_CREATOR_WORK"

        # 2. Money Gate
        if requires_payment or raw_status == "PAYMENT_APPROVAL_REQUIRED":
            return WorkReadinessState.MONEY_GATE, f"REQUIRES_PAYMENT_{cost}_EUR"

        # 3. Publication & Upload Gate
        if task_type in ("PUBLICATION", "UPLOAD", "PUBLIC_DISTRIBUTION", "TIKTOK_PUBLISH", "YOUTUBE_PUBLISH"):
            return WorkReadinessState.PUBLICATION_GATE, "REQUIRES_HUMAN_PUBLICATION_APPROVAL"

        # 4. Human / Identity / Legal Gate
        if requires_human or raw_status in ("WAITING_FOR_HUMAN", "HUMAN_GATE", "HUMAN_AUDIENCE_GATED"):
            return WorkReadinessState.HUMAN_GATE, "REQUIRES_HUMAN_APPROVAL"

        text_content = f"{obj} {task_type} {' '.join(scope)}".upper()
        if any(m in text_content for m in ("OAUTH", "2FA", "PASSWORD", "KYC", "LEGAL_SIGNATURE")):
            return WorkReadinessState.HUMAN_GATE, "REQUIRES_HUMAN_CREDENTIAL_OR_IDENTITY"

        # 5. Completed Check (Direct ID or Fingerprint in historical ledger)
        fp = compute_canonical_work_fingerprint(obj, scope, task_type)
        if raw_status == "COMPLETED" or self.is_fingerprint_completed(fp) or self.is_fingerprint_completed(opp_id):
            return WorkReadinessState.COMPLETED, "ALREADY_COMPLETED_IN_HISTORICAL_LEDGER"

        # 6. Busywork / No Information Gain Check
        if any(bw in obj.lower() for bw in BUSYWORK_KEYWORDS):
            return WorkReadinessState.NO_INFORMATION_GAIN, "REJECTED_AS_BUSYWORK_OR_ZERO_INFO_GAIN"

        # 7. Circuit Breaker Check (Consecutive Failures)
        breaker_file = self.circuit_breakers_dir / f"{fp}.json"
        if breaker_file.is_file():
            try:
                b_data = json.loads(breaker_file.read_text(encoding="utf-8"))
                if b_data.get("status") == "OPEN":
                    return WorkReadinessState.BLOCKED_EXTERNAL, f"CIRCUIT_BREAKER_OPEN_{b_data.get('reason')}"
            except Exception:
                pass

        # 8. Stale State / Missing Source Artifact Check
        source_artifact = str(opp_dict.get("source_artifact", ""))
        if source_artifact:
            art_path = self.repo_dir / source_artifact
            if not art_path.exists():
                return WorkReadinessState.STALE, f"REFERENCED_ARTIFACT_MISSING_{source_artifact}"

        # 9. Ready Classification by Value
        priority = int(opp_dict.get("priority", 5))
        if priority >= 8 or task_type in ("UNIT_TEST_FIX", "CRASH_RECOVERY", "SECURITY_AUDIT", "FAILING_TEST_REMEDIATION"):
            return WorkReadinessState.READY_HIGH_VALUE, None
        elif priority >= 4:
            return WorkReadinessState.READY_USEFUL, None
        else:
            return WorkReadinessState.NEUTRAL, None

    # =========================================================================
    # PHASE C: EMPTY-QUEUE GROUNDED LOCAL DISCOVERY
    # =========================================================================
    def discover_grounded_useful_work(self) -> List[ScoredCandidateTask]:
        """Scans local repository state across 8 grounded priority tiers when explicit queue is empty."""
        discovered: List[ScoredCandidateTask] = []

        # Tier 1: Check for Failing Deterministic Tests
        tier1 = self._discover_tier1_failing_tests()
        discovered.extend(tier1)

        # Tier 2: Check for Unresolved Concrete Defects / Circuit Breakers
        tier2 = self._discover_tier2_concrete_defects()
        discovered.extend(tier2)

        # Tier 3: Stale Authoritative-State Reconciliation (e.g. dead lock files)
        tier3 = self._discover_tier3_state_reconciliation()
        discovered.extend(tier3)

        # Tier 4: Missing Regression Test Coverage for Active Scripts
        tier4 = self._discover_tier4_missing_test_coverage()
        discovered.extend(tier4)

        # Tier 5: Code Quality & Reliability Defects (e.g. trailing whitespace, diff check)
        tier5 = self._discover_tier5_code_quality_defects()
        discovered.extend(tier5)

        # Tier 6: Local Inventory & Manifest Reconciliation
        tier6 = self._discover_tier6_manifest_reconciliation()
        discovered.extend(tier6)

        # Tier 7: Automation Reliability & Idempotency Hardening
        tier7 = self._discover_tier7_automation_hardening()
        discovered.extend(tier7)

        # Tier 8: Pre-approved Prepared Useful Tasks (Zero Gate)
        tier8 = self._discover_tier8_prepared_tasks()
        discovered.extend(tier8)

        # Filter out duplicates and score remaining
        valid_scored: List[ScoredCandidateTask] = []
        seen_fps: Set[str] = set()

        for cand in discovered:
            if cand.fingerprint in self._completed_fingerprints or cand.fingerprint in seen_fps:
                continue
            seen_fps.add(cand.fingerprint)
            cand.final_score = self.calculate_score(cand)
            cand.is_actionable = cand.readiness_state in (
                WorkReadinessState.READY_HIGH_VALUE,
                WorkReadinessState.READY_USEFUL,
                WorkReadinessState.NEUTRAL,
            )
            valid_scored.append(cand)

        # Sort strictly by final_score descending, then task_id for determinism
        valid_scored.sort(key=lambda x: (x.final_score, x.task_id), reverse=True)
        return valid_scored

    def _discover_tier1_failing_tests(self) -> List[ScoredCandidateTask]:
        """Tier 1: Check for any failing unit tests."""
        tasks = []
        # Check if any known failure record exists
        test_reports = list((self.events_dir / "test-reports").glob("*.json")) if (self.events_dir / "test-reports").exists() else []
        for tr in test_reports:
            try:
                data = json.loads(tr.read_text(encoding="utf-8"))
                if data.get("status") == "FAILED" and data.get("failing_module"):
                    mod = data["failing_module"]
                    fp = compute_canonical_work_fingerprint(f"Fix failing test {mod}", [mod], "FAILING_TEST_REMEDIATION")
                    tasks.append(ScoredCandidateTask(
                        task_id=f"TASK-T1-FIX-{Path(mod).stem}",
                        objective=f"Remediate failing deterministic test suite in {mod}",
                        readiness_state=WorkReadinessState.READY_HIGH_VALUE,
                        task_type="FAILING_TEST_REMEDIATION",
                        scope=[mod],
                        value_score=10.0,
                        information_gain=10.0,
                        risk_score=1.0,
                        fingerprint=fp,
                        evidence={"failing_module": mod, "report": str(tr)},
                    ))
            except Exception:
                pass
        return tasks

    def _discover_tier2_concrete_defects(self) -> List[ScoredCandidateTask]:
        """Tier 2: Check for unhandled exceptions or open circuit breakers."""
        tasks = []
        for bf in self.circuit_breakers_dir.glob("*.json"):
            try:
                data = json.loads(bf.read_text(encoding="utf-8"))
                if data.get("status") == "OPEN" and data.get("consecutive_failures", 0) >= 2:
                    fp = compute_canonical_work_fingerprint(f"Investigate circuit breaker {bf.stem}", ["events/circuit-breakers"], "DEFECT_INVESTIGATION")
                    tasks.append(ScoredCandidateTask(
                        task_id=f"TASK-T2-BREAKER-{bf.stem[:8]}",
                        objective=f"Investigate and remediate open circuit breaker {bf.stem}",
                        readiness_state=WorkReadinessState.READY_HIGH_VALUE,
                        task_type="DEFECT_INVESTIGATION",
                        scope=["events/circuit-breakers"],
                        value_score=9.0,
                        information_gain=9.0,
                        risk_score=1.0,
                        fingerprint=fp,
                        evidence=data,
                    ))
            except Exception:
                pass
        return tasks

    def _discover_tier3_state_reconciliation(self) -> List[ScoredCandidateTask]:
        """Tier 3: Check for orphaned lock files or dead PID claims."""
        tasks = []
        locks_dir = self.events_dir / "locks"
        if locks_dir.exists():
            orphaned = []
            for lf in locks_dir.glob("*.lock"):
                try:
                    data = json.loads(lf.read_text(encoding="utf-8"))
                    pid = data.get("pid")
                    if pid and not self._is_pid_alive(pid):
                        orphaned.append(str(lf.name))
                except Exception:
                    pass
            if orphaned:
                fp = compute_canonical_work_fingerprint(f"Reclaim {len(orphaned)} orphaned lock files", ["events/locks"], "STATE_RECONCILIATION")
                tasks.append(ScoredCandidateTask(
                    task_id=f"TASK-T3-LOCK-RECLAIM-{len(orphaned)}",
                    objective=f"Reclaim {len(orphaned)} orphaned scope locks held by dead processes",
                    readiness_state=WorkReadinessState.READY_HIGH_VALUE,
                    task_type="STATE_RECONCILIATION",
                    scope=["events/locks"],
                    value_score=8.5,
                    information_gain=8.0,
                    risk_score=1.0,
                    fingerprint=fp,
                    evidence={"orphaned_locks": orphaned},
                ))
        return tasks

    def _discover_tier4_missing_test_coverage(self) -> List[ScoredCandidateTask]:
        """Tier 4: Check for active scripts in scripts/ lacking a unit test in tests/."""
        tasks = []
        scripts_path = self.repo_dir / "scripts"
        tests_path = self.repo_dir / "tests"
        if scripts_path.is_dir() and tests_path.is_dir():
            for sf in sorted(scripts_path.glob("*.py")):
                if sf.name.startswith("__"):
                    continue
                tf = tests_path / f"test_{sf.name}"
                if not tf.exists():
                    fp = compute_canonical_work_fingerprint(f"Add unit test for {sf.name}", [f"scripts/{sf.name}", f"tests/test_{sf.name}"], "REGRESSION_TEST_COVERAGE")
                    tasks.append(ScoredCandidateTask(
                        task_id=f"TASK-T4-TEST-GAP-{sf.stem}",
                        objective=f"Add deterministic regression test suite for scripts/{sf.name}",
                        readiness_state=WorkReadinessState.READY_USEFUL,
                        task_type="REGRESSION_TEST_COVERAGE",
                        scope=[f"scripts/{sf.name}", f"tests/test_{sf.name}"],
                        value_score=7.0,
                        information_gain=7.5,
                        risk_score=1.0,
                        fingerprint=fp,
                        evidence={"target_script": str(sf.relative_to(self.repo_dir))},
                    ))
                    # Bound to at most 2 missing test tasks per scan
                    if len(tasks) >= 2:
                        break
        return tasks

    def _discover_tier5_code_quality_defects(self) -> List[ScoredCandidateTask]:
        """Tier 5: Check git diff --check for trailing whitespace or formatting defects."""
        tasks = []
        try:
            res = subprocess.run(["git", "diff", "--check"], cwd=str(self.repo_dir), capture_output=True, text=True, timeout=5)
            if res.returncode != 0 and res.stdout.strip():
                fp = compute_canonical_work_fingerprint("Fix git diff whitespace warnings", ["repo/local"], "CODE_QUALITY_AUDIT")
                tasks.append(ScoredCandidateTask(
                    task_id="TASK-T5-DIFF-CHECK-REMEDIATION",
                    objective="Fix whitespace and formatting defects detected by git diff --check",
                    readiness_state=WorkReadinessState.READY_USEFUL,
                    task_type="CODE_QUALITY_AUDIT",
                    scope=["repo/local"],
                    value_score=6.0,
                    information_gain=5.0,
                    risk_score=1.0,
                    fingerprint=fp,
                    evidence={"diff_output": res.stdout[:500]},
                ))
        except Exception:
            pass
        return tasks

    def _discover_tier6_manifest_reconciliation(self) -> List[ScoredCandidateTask]:
        """Tier 6: Check disaster recovery manifest and capacity metrics freshness."""
        tasks = []
        dr_file = self.events_dir / "host-survival" / "disaster_recovery_manifest.json"
        if dr_file.exists():
            try:
                data = json.loads(dr_file.read_text(encoding="utf-8"))
                age = time.time() - dr_file.stat().st_mtime
                if age > 86400:  # Older than 24h
                    fp = compute_canonical_work_fingerprint("Refresh stale disaster recovery manifest", ["events/host-survival"], "MANIFEST_RECONCILIATION")
                    tasks.append(ScoredCandidateTask(
                        task_id="TASK-T6-DR-MANIFEST-REFRESH",
                        objective="Re-verify and refresh 24h+ stale disaster recovery manifest",
                        readiness_state=WorkReadinessState.READY_USEFUL,
                        task_type="MANIFEST_RECONCILIATION",
                        scope=["events/host-survival"],
                        value_score=5.5,
                        information_gain=6.0,
                        risk_score=1.0,
                        fingerprint=fp,
                        evidence={"manifest_age_hours": round(age / 3600, 1)},
                    ))
            except Exception:
                pass
        return tasks

    def _discover_tier7_automation_hardening(self) -> List[ScoredCandidateTask]:
        """Tier 7: Check queue hygiene archive manifest status."""
        tasks = []
        q_dir = self.events_dir / "opportunity-queue"
        if q_dir.exists():
            unarchived = list(q_dir.glob("*.json"))
            if len(unarchived) > 20:
                fp = compute_canonical_work_fingerprint(f"Archive {len(unarchived)} historical queue files", ["events/opportunity-queue"], "QUEUE_HYGIENE")
                tasks.append(ScoredCandidateTask(
                    task_id=f"TASK-T7-QUEUE-HYGIENE-{len(unarchived)}",
                    objective=f"Prune and archive {len(unarchived)} historical opportunity queue files",
                    readiness_state=WorkReadinessState.READY_USEFUL,
                    task_type="QUEUE_HYGIENE",
                    scope=["events/opportunity-queue"],
                    value_score=5.0,
                    information_gain=4.0,
                    risk_score=1.0,
                    fingerprint=fp,
                    evidence={"unarchived_count": len(unarchived)},
                ))
        return tasks

    def _discover_tier8_prepared_tasks(self) -> List[ScoredCandidateTask]:
        """Tier 8: Zero-gate prepared tasks (e.g. inbound response polling or KIbey delivery harness test)."""
        tasks = []
        kibey_harness = self.repo_dir / "scripts" / "run_kibey_delivery_proof.py"
        if kibey_harness.exists():
            fp = compute_canonical_work_fingerprint("Execute KIbey router delivery proof", ["events/revenue-opportunities"], "PREPARED_VALIDATION")
            tasks.append(ScoredCandidateTask(
                task_id="TASK-T8-KIBEY-PROOF-VALIDATION",
                objective="Execute deterministic KIbey router delivery proof test",
                readiness_state=WorkReadinessState.READY_USEFUL,
                task_type="PREPARED_VALIDATION",
                scope=["events/revenue-opportunities"],
                value_score=4.5,
                information_gain=4.0,
                risk_score=1.0,
                fingerprint=fp,
                evidence={"script": "scripts/run_kibey_delivery_proof.py"},
            ))
        return tasks

    # =========================================================================
    # PHASE D: DETERMINISTIC SCORING MODEL
    # =========================================================================
    def calculate_score(self, cand: ScoredCandidateTask) -> float:
        """Calculates deterministic composite score. Hard gates strictly override score to 0."""
        # Hard Gate Overrides
        if cand.readiness_state in (
            WorkReadinessState.MONEY_GATE,
            WorkReadinessState.HUMAN_GATE,
            WorkReadinessState.PUBLICATION_GATE,
            WorkReadinessState.PROTECTED_BOUNDARY_GATED,
            WorkReadinessState.COMPLETED,
            WorkReadinessState.DUPLICATE,
            WorkReadinessState.NO_INFORMATION_GAIN,
            WorkReadinessState.BLOCKED_EXTERNAL,
            WorkReadinessState.STALE,
        ):
            return 0.0

        w_val = 0.35
        w_info = 0.25
        w_risk = 0.15
        w_readiness = 0.15
        w_recency = 0.05
        w_verify = 0.05

        # Normalize components 0.0 - 10.0
        val = min(10.0, max(0.0, cand.value_score))
        info = min(10.0, max(0.0, cand.information_gain))
        risk_penalty = min(10.0, max(0.0, cand.risk_score))
        dep_readiness = min(10.0, max(0.0, cand.dependency_readiness))
        recency = min(10.0, max(0.0, cand.recency_score))
        verify_penalty = min(10.0, max(0.0, cand.time_to_verify_seconds / 10.0))

        score = (
            w_val * val
            + w_info * info
            - w_risk * risk_penalty
            + w_readiness * dep_readiness
            + w_recency * recency
            - w_verify * verify_penalty
        )
        return round(max(0.0, score), 3)

    # =========================================================================
    # PHASE E: AUTONOMY STATE LIFECYCLE
    # =========================================================================
    def select_next_task(self, explicit_queue: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Selects the single best actionable task from explicit queue or grounded discovery."""
        try:
            from scripts.single_flight import is_single_flight_locked
        except ImportError:
            from single_flight import is_single_flight_locked
        if is_single_flight_locked(self.repo_dir):
            return {"status": "BLOCKED", "reason": "SINGLE_FLIGHT_LOCKED"}

        evaluated_candidates: List[ScoredCandidateTask] = []

        # 1. Evaluate explicit queue candidates
        for opp in explicit_queue:
            state, reason = self.classify_opportunity(opp)
            obj = str(opp.get("objective", opp.get("description", "")))
            scope = list(opp.get("allowed_scope", opp.get("scope", [])))
            task_type = str(opp.get("task_type", opp.get("source", ""))).upper()
            fp = compute_canonical_work_fingerprint(obj, scope, task_type)

            cand = ScoredCandidateTask(
                task_id=str(opp.get("opportunity_id", f"TASK-{fp[:8]}")),
                objective=obj,
                readiness_state=state,
                task_type=task_type,
                scope=scope,
                project=str(opp.get("project", "2026-courier")),
                value_score=float(opp.get("priority", 5.0)),
                information_gain=5.0,
                risk_score=1.0 if state in (WorkReadinessState.READY_HIGH_VALUE, WorkReadinessState.READY_USEFUL) else 5.0,
                dependency_readiness=10.0 if not opp.get("dependencies") else 5.0,
                fingerprint=fp,
                gate_reason=reason,
                evidence=dict(opp.get("evidence", {})),
            )
            cand.final_score = self.calculate_score(cand)
            cand.is_actionable = state in (WorkReadinessState.READY_HIGH_VALUE, WorkReadinessState.READY_USEFUL, WorkReadinessState.NEUTRAL)
            evaluated_candidates.append(cand)

        # Filter actionable explicit candidates
        actionable = [c for c in evaluated_candidates if c.is_actionable]

        # 2. If no actionable explicit candidates, execute Grounded Local Discovery
        if not actionable:
            discovery_candidates = self.discover_grounded_useful_work()
            actionable = [c for c in discovery_candidates if c.is_actionable]

        if not actionable:
            # Genuinely NO SAFE USEFUL WORK available
            return {
                "lifecycle_state": AutonomyLifecycleState.SAFE_IDLE.value,
                "action": "ENTER_SAFE_IDLE",
                "selected_task": None,
                "reason": "NO_SAFE_USEFUL_WORK_AVAILABLE",
                "all_evaluated_count": len(evaluated_candidates),
            }

        # Deterministic winner selection: score descending, then task_id string
        actionable.sort(key=lambda x: (x.final_score, x.task_id), reverse=True)
        winner = actionable[0]

        return {
            "lifecycle_state": AutonomyLifecycleState.TASK_RUNNING.value,
            "action": "DISPATCH_TASK",
            "selected_task": winner.to_dict(),
            "reason": f"SELECTED_HIGHEST_SCORE_{winner.final_score}",
            "candidate_pool_size": len(actionable),
        }

    def _is_pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def main() -> int:
    engine = UsefulWorkSelectionEngine()
    q_file = engine.events_dir / "autonomy-dispatcher" / "dispatch_queue.json"
    queue = []
    if q_file.is_file():
        try:
            queue = json.loads(q_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    res = engine.select_next_task(queue)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

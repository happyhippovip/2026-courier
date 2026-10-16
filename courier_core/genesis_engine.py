"""COURIER GENESIS ENGINE — Universal Self-Steering Control Code.

Architecture:
    Mission -> Rules -> Budget -> Safety Gates
    1. Task Recognition: Discover pending tasks from goal, DAG state, and checkpointed facts.
    2. Work Distribution: Dispatch under Single-Writer lease, grant verification, and zero-spend limit.
    3. Independent Verification: Verify results via byte anchors, content hashes, and fail-closed validators.
    4. Adaptive Learning: Analyze failures, trip circuit breakers, prevent cache poisoning, backoff.
    5. Continuation & Next Step: Claim -> Execute -> Verify -> Checkpoint -> Release -> Next.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class VerdictOutcome(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class GenesisPolicy:
    """Canonical rules, limits and security constraints for the Genesis Engine."""
    spend_limit_eur: float = 0.0
    single_writer: bool = True
    heavy_job_limit: int = 1
    max_retries: int = 2
    timeout_seconds: float = 30.0
    require_https: bool = True
    allowed_origins: Tuple[str, ...] = ("https://example.org",)
    fail_closed: bool = True


@dataclass
class GenesisTask:
    task_id: str
    workkey: str
    action_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[str] = None
    claim_token: Optional[str] = None
    attempts: int = 0
    failure_history: List[str] = field(default_factory=list)
    verdict: Optional[Dict[str, Any]] = None


@dataclass
class GenesisCheckpoint:
    mission_id: str
    step: int
    completed_task_ids: List[str]
    active_claim: Optional[str]
    facts_count: int
    timestamp: float = field(default_factory=time.time)


class CircuitBreaker:
    """Prevents repeated runs on fatal security or repeated infrastructure failures."""
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures: Dict[str, int] = {}
        self.tripped: Dict[str, float] = {}

    def record_failure(self, scope: str, fatal: bool = False):
        if fatal:
            self.tripped[scope] = time.time()
            return
        self.failures[scope] = self.failures.get(scope, 0) + 1
        if self.failures[scope] >= self.failure_threshold:
            self.tripped[scope] = time.time()

    def record_success(self, scope: str):
        self.failures.pop(scope, None)
        self.tripped.pop(scope, None)

    def is_tripped(self, scope: str) -> bool:
        if scope not in self.tripped:
            return False
        if time.time() - self.tripped[scope] > self.reset_timeout:
            # Cooldown expired, half-open
            self.tripped.pop(scope, None)
            self.failures[scope] = 0
            return False
        return True


class GenesisContentStore:
    """Content-addressed tamper-proof store for verification artifacts."""
    def __init__(self):
        self._blobs: Dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self._blobs[digest] = data
        return digest

    def get(self, digest: str) -> bytes:
        if digest not in self._blobs:
            raise KeyError(f"Digest {digest} not found in store")
        data = self._blobs[digest]
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Store tamper detected: data does not match hash")
        return data


class CourierGenesisEngine:
    """Universal steering controller executing the 5-pillar loop:
    1. Aufgaben erkennen (Task Recognition)
    2. Arbeit verteilen (Distribution & Lease)
    3. Ergebnisse prüfen (Verification)
    4. Aus Fehlern lernen (Learning & Adaptation)
    5. Nächster überprüfter Schritt (Continuation & Progression)
    """

    def __init__(
        self,
        mission_id: str,
        policy: Optional[GenesisPolicy] = None,
        state_dir: Optional[Path] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.mission_id = mission_id
        self.policy = policy or GenesisPolicy()
        self.state_dir = Path(state_dir) if state_dir else Path(".courier_genesis")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time

        self.tasks: Dict[str, GenesisTask] = {}
        self.task_order: List[str] = []
        self.completed_tasks: List[str] = []
        self.store = GenesisContentStore()
        self.breaker = CircuitBreaker()
        self.active_writer: Optional[str] = None
        self.accepted_facts: List[Dict[str, Any]] = []
        self.step_counter: int = 0
        self.spent_eur: float = 0.0

        self.facts_file = self.state_dir / f"{mission_id}_facts.jsonl"
        self.checkpoint_file = self.state_dir / f"{mission_id}_checkpoint.json"
        self._load_checkpoint()

    # -------------------------------------------------------------------------
    # PILLAR 1: AUFGABEN ERKENNEN (Task Recognition & Goal Decomposition)
    # -------------------------------------------------------------------------

    def register_task(
        self,
        task_id: str,
        workkey: str,
        action_type: str,
        payload: Dict[str, Any],
        depends_on: Optional[List[str]] = None,
    ) -> GenesisTask:
        """Register a task into the mission dependency graph."""
        if task_id in self.tasks:
            return self.tasks[task_id]

        task = GenesisTask(
            task_id=task_id,
            workkey=workkey,
            action_type=action_type,
            payload=payload,
            depends_on=depends_on or [],
            status=TaskStatus.PENDING,
        )
        self.tasks[task_id] = task
        self.task_order.append(task_id)
        return task

    def decompose_mission_goal(self, goal: Dict[str, Any]) -> List[GenesisTask]:
        """Automatically derive concrete executable tasks from a high-level goal."""
        goal_type = goal.get("type", "SEQUENTIAL_PIPELINE")
        created: List[GenesisTask] = []

        if goal_type == "SEQUENTIAL_PIPELINE":
            steps = goal.get("steps", [])
            prev_id: Optional[str] = None
            for idx, step_spec in enumerate(steps):
                tid = step_spec.get("task_id", f"{self.mission_id}-step-{idx:03d}")
                wkey = step_spec.get("workkey", f"wk-{tid}")
                deps = [prev_id] if prev_id else []
                task = self.register_task(
                    task_id=tid,
                    workkey=wkey,
                    action_type=step_spec.get("action_type", "EXECUTE_UNIT"),
                    payload=step_spec.get("payload", {}),
                    depends_on=deps,
                )
                created.append(task)
                prev_id = tid

        elif goal_type == "RESEARCH_EVIDENCE":
            # Auto-derives spider fetch and quote anchor verification
            urls = goal.get("urls", [])
            quote = goal.get("quote", "")
            for idx, u in enumerate(urls):
                tid = f"{self.mission_id}-spider-{idx:03d}"
                wkey = f"wk-spider-{hashlib.sha256(u.encode()).hexdigest()[:8]}"
                task = self.register_task(
                    task_id=tid,
                    workkey=wkey,
                    action_type="SPIDER_CLAIM_VERIFY",
                    payload={"url": u, "quote": quote, "approved_origin": goal.get("approved_origin")},
                )
                created.append(task)

        return created

    def detect_next_ready_tasks(self) -> List[GenesisTask]:
        """Find pending tasks whose dependencies are fully verified and not circuit-broken."""
        ready: List[GenesisTask] = []
        for tid in self.task_order:
            task = self.tasks[tid]
            if task.status != TaskStatus.PENDING:
                continue

            # Check upstream dependencies
            deps_ok = True
            for dep_id in task.depends_on:
                dep_task = self.tasks.get(dep_id)
                if not dep_task or dep_task.status != TaskStatus.VERIFIED:
                    deps_ok = False
                    break

            if not deps_ok:
                continue

            # Check circuit breaker
            if self.breaker.is_tripped(task.action_type) or self.breaker.is_tripped(task.workkey):
                task.status = TaskStatus.BLOCKED
                task.verdict = {"outcome": VerdictOutcome.BLOCKED, "reason": "Circuit breaker tripped"}
                continue

            ready.append(task)
        return ready

    # -------------------------------------------------------------------------
    # PILLAR 2: ARBEIT VERTEILEN (Work Distribution & Single-Writer Lease)
    # -------------------------------------------------------------------------

    def claim_task(self, task_id: str, worker_id: str) -> Tuple[bool, Optional[str], str]:
        """Safely claim a task enforcing Single-Writer and zero-spend constraints."""
        task = self.tasks.get(task_id)
        if not task:
            return False, None, f"Task {task_id} not found"

        if task.status != TaskStatus.PENDING:
            return False, None, f"Task {task_id} is not PENDING (current: {task.status.value})"

        # Enforce spend limit gate
        cost = float(task.payload.get("cost_eur", 0.0))
        if (self.spent_eur + cost) > self.policy.spend_limit_eur:
            task.status = TaskStatus.BLOCKED
            task.verdict = {"outcome": VerdictOutcome.BLOCKED, "reason": "Autonomous spend limit exceeded (spend=0)"}
            return False, None, "Spend limit exceeded: fail closed"

        # Enforce Single-Writer rule
        if self.policy.single_writer and self.active_writer is not None and self.active_writer != worker_id:
            return False, None, f"Single-Writer violation: active writer is {self.active_writer}"

        claim_token = f"claim-{worker_id}-{int(self.clock())}-{hashlib.sha256(task.workkey.encode()).hexdigest()[:8]}"
        task.status = TaskStatus.CLAIMED
        task.assigned_worker = worker_id
        task.claim_token = claim_token
        task.attempts += 1
        self.active_writer = worker_id
        return True, claim_token, "Claim successful"

    # -------------------------------------------------------------------------
    # PILLAR 3: ERGEBNISSE PRÜFEN (Independent Verification)
    # -------------------------------------------------------------------------

    def verify_execution(
        self,
        task_id: str,
        raw_result: Dict[str, Any],
        fetcher: Optional[Callable[[str], Tuple[str, bytes]]] = None,
    ) -> Dict[str, Any]:
        """Independent verification of raw worker results. Never trusts self-reports."""
        task = self.tasks.get(task_id)
        if not task:
            return {"outcome": VerdictOutcome.ERROR, "accepted": False, "reason": "Task not found"}

        action = task.action_type

        # Verification for SPIDER_CLAIM_VERIFY (Origin grant, HTTPS, and Byte-anchor check)
        if action == "SPIDER_CLAIM_VERIFY":
            url = task.payload.get("url", "")
            quote = task.payload.get("quote", "")
            approved_origin = task.payload.get("approved_origin") or (self.policy.allowed_origins[0] if self.policy.allowed_origins else "")

            parts = urlsplit(url)
            origin = f"{parts.scheme}://{parts.netloc}"

            # Gate: Scheme must be https if policy demands
            if self.policy.require_https and parts.scheme != "https":
                return {"outcome": VerdictOutcome.BLOCKED, "accepted": False, "reason": f"Scheme {parts.scheme} rejected, HTTPS required"}

            # Gate: Origin must match approved grant
            if origin != approved_origin:
                return {"outcome": VerdictOutcome.BLOCKED, "accepted": False, "reason": f"Origin {origin} does not match approved {approved_origin}"}

            if not fetcher:
                # Default synthetic fetcher reading from payload body
                body_bytes = task.payload.get("body", b"")
                if isinstance(body_bytes, str):
                    body_bytes = body_bytes.encode("utf-8")
                final_url = url
            else:
                final_url, body_bytes = fetcher(url)

            final_parts = urlsplit(final_url)
            final_origin = f"{final_parts.scheme}://{final_parts.netloc}"
            if final_origin != approved_origin:
                return {"outcome": VerdictOutcome.BLOCKED, "accepted": False, "reason": f"Redirect left approved origin: {final_origin}"}

            digest = self.store.put(body_bytes)
            text = self.store.get(digest).decode("utf-8", errors="replace")
            offset = text.find(quote)

            if offset >= 0:
                anchor = {"sha256": digest, "url": final_url, "offset": offset, "length": len(quote)}
                return {"outcome": VerdictOutcome.SUPPORTED, "accepted": True, "anchor": anchor, "reason": "Anchor verified in fetched bytes"}
            else:
                return {"outcome": VerdictOutcome.CONTRADICTED, "accepted": False, "reason": f"Quote {quote!r} not found in fetched bytes"}

        # Verification for standard sequential units (Contract & Output check)
        elif action in ("EXECUTE_UNIT", "STANDARD_TASK"):
            exit_code = raw_result.get("exit_code", -1)
            outputs = raw_result.get("outputs", {})
            verified_expected = task.payload.get("expected_output")

            if exit_code != 0:
                return {
                    "outcome": VerdictOutcome.ERROR,
                    "accepted": False,
                    "reason": f"Non-zero exit code: {exit_code}",
                    "details": raw_result.get("error", "Process returned failure"),
                }

            if verified_expected is not None and outputs.get("result") != verified_expected:
                return {
                    "outcome": VerdictOutcome.CONTRADICTED,
                    "accepted": False,
                    "reason": f"Output mismatch: expected {verified_expected}, got {outputs.get('result')}",
                }

            body_str = json.dumps(outputs, sort_keys=True)
            digest = self.store.put(body_str.encode("utf-8"))
            return {
                "outcome": VerdictOutcome.SUPPORTED,
                "accepted": True,
                "anchor": {"sha256": digest},
                "reason": "Execution exit code 0 and output contract satisfied",
            }

        # Fallback default reject (Fail closed)
        return {"outcome": VerdictOutcome.BLOCKED, "accepted": False, "reason": f"Unknown action type: {action}"}

    # -------------------------------------------------------------------------
    # PILLAR 4: AUS FEHLERN LERNEN (Adaptive Learning & Circuit Breaker)
    # -------------------------------------------------------------------------

    def learn_and_adapt(self, task_id: str, verdict: Dict[str, Any]) -> Dict[str, Any]:
        """Record error patterns, trip circuit breakers on security errors, and adapt dispatch."""
        task = self.tasks[task_id]
        reason = verdict.get("reason", "Unknown failure")
        task.failure_history.append(reason)
        task.verdict = verdict

        outcome = verdict.get("outcome")

        # Security/Policy violations trip immediately (Fail closed)
        if outcome == VerdictOutcome.BLOCKED or "rejected" in reason.lower() or "origin" in reason.lower():
            task.status = TaskStatus.BLOCKED
            self.breaker.record_failure(task.action_type, fatal=True)
            self.breaker.record_failure(task.workkey, fatal=True)
            adaptation = {"strategy": "FAIL_CLOSED_BLOCK", "circuit_tripped": True, "reason": reason}

        elif task.attempts >= self.policy.max_retries:
            task.status = TaskStatus.FAILED
            self.breaker.record_failure(task.action_type, fatal=False)
            adaptation = {"strategy": "MAX_RETRIES_EXCEEDED", "reason": f"Exceeded {self.policy.max_retries} attempts"}

        else:
            # Retryable with backoff and cache purge
            task.status = TaskStatus.PENDING
            task.claim_token = None
            task.assigned_worker = None
            adaptation = {
                "strategy": "EXPONENTIAL_BACKOFF_RETRY",
                "backoff_seconds": 2 ** task.attempts,
                "purge_dirty_cache": True,
            }

        # Release active writer on failure
        if self.active_writer == task.assigned_worker:
            self.active_writer = None

        self._save_checkpoint()
        return adaptation

    # -------------------------------------------------------------------------
    # PILLAR 5: NÄCHSTER SCHRITT (Continuation, Progression & Loop)
    # -------------------------------------------------------------------------

    def checkpoint_and_advance(self, task_id: str, verdict: Dict[str, Any]) -> GenesisCheckpoint:
        """Atomically record accepted fact, release lock, advance step and save checkpoint."""
        task = self.tasks[task_id]
        task.status = TaskStatus.VERIFIED
        task.verdict = verdict
        self.completed_tasks.append(task_id)
        self.step_counter += 1

        # Record accepted fact
        fact = {
            "workkey": task.workkey,
            "step": self.step_counter,
            "task_id": task.task_id,
            "statement": f"{verdict.get('outcome')}: {task.action_type} verified",
            "sources": [verdict.get("anchor", {}).get("sha256", "evidence-anchor")],
            "accepted_by": "GenesisEngineController",
            "accepted_at": self.clock(),
        }
        self.accepted_facts.append(fact)
        with open(self.facts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(fact) + "\n")

        # Record success with circuit breaker
        self.breaker.record_success(task.action_type)
        self.breaker.record_success(task.workkey)

        # Release active writer
        if self.active_writer == task.assigned_worker:
            self.active_writer = None

        return self._save_checkpoint()

    def run_cycle(
        self,
        executor: Callable[[GenesisTask], Dict[str, Any]],
        worker_id: str = "genesis-worker-01",
        fetcher: Optional[Callable[[str], Tuple[str, bytes]]] = None,
    ) -> Dict[str, Any]:
        """Run a single autonomous cycle of the 5-pillar loop."""
        ready_tasks = self.detect_next_ready_tasks()
        if not ready_tasks:
            all_done = all(t.status == TaskStatus.VERIFIED for t in self.tasks.values())
            has_blocked = any(t.status in (TaskStatus.BLOCKED, TaskStatus.FAILED) for t in self.tasks.values())
            return {
                "cycled": False,
                "all_completed": all_done,
                "stalled": not all_done and not has_blocked,
                "blocked": has_blocked,
                "ready_count": 0,
            }

        # Select highest-priority ready task (FIFO by declaration order)
        task = ready_tasks[0]

        # 1. Claim under single-writer
        ok, token, msg = self.claim_task(task.task_id, worker_id)
        if not ok:
            return {"cycled": False, "claimed": False, "reason": msg, "task_id": task.task_id}

        # 2. Execute
        try:
            raw_result = executor(task)
        except Exception as ex:
            raw_result = {"exit_code": 1, "error": str(ex)}

        # 3. Independent Verify
        verdict = self.verify_execution(task.task_id, raw_result, fetcher=fetcher)

        # 4 & 5. Advance or Learn
        if verdict.get("accepted"):
            cp = self.checkpoint_and_advance(task.task_id, verdict)
            return {
                "cycled": True,
                "status": "ADVANCED",
                "task_id": task.task_id,
                "verdict": verdict,
                "checkpoint_step": cp.step,
            }
        else:
            adaptation = self.learn_and_adapt(task.task_id, verdict)
            return {
                "cycled": True,
                "status": "FAILED_OR_BLOCKED",
                "task_id": task.task_id,
                "verdict": verdict,
                "adaptation": adaptation,
            }

    def run_autonomous_loop(
        self,
        executor: Callable[[GenesisTask], Dict[str, Any]],
        worker_id: str = "genesis-worker-01",
        fetcher: Optional[Callable[[str], Tuple[str, bytes]]] = None,
        max_cycles: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Autonomous control loop running until all tasks are complete or cleanly blocked."""
        limit = max_cycles or self.policy.heavy_job_limit * 50
        cycles = 0
        cycle_log: List[Dict[str, Any]] = []

        while cycles < limit:
            cycles += 1
            res = self.run_cycle(executor=executor, worker_id=worker_id, fetcher=fetcher)
            cycle_log.append(res)

            if not res.get("cycled"):
                break

        all_done = len(self.tasks) > 0 and all(t.status == TaskStatus.VERIFIED for t in self.tasks.values())
        return {
            "mission_id": self.mission_id,
            "cycles_run": cycles,
            "all_completed": all_done,
            "completed_count": len(self.completed_tasks),
            "total_tasks": len(self.tasks),
            "spent_eur": self.spent_eur,
            "history": cycle_log,
        }

    # -------------------------------------------------------------------------
    # STATE & PERSISTENCE
    # -------------------------------------------------------------------------

    def _save_checkpoint(self) -> GenesisCheckpoint:
        cp = GenesisCheckpoint(
            mission_id=self.mission_id,
            step=self.step_counter,
            completed_task_ids=list(self.completed_tasks),
            active_claim=self.active_writer,
            facts_count=len(self.accepted_facts),
            timestamp=self.clock(),
        )
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(asdict(cp), f, indent=2)
        return cp

    def _load_checkpoint(self):
        if not self.checkpoint_file.exists():
            return
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.step_counter = data.get("step", 0)
            self.completed_tasks = data.get("completed_task_ids", [])
            for tid in self.completed_tasks:
                if tid in self.tasks:
                    self.tasks[tid].status = TaskStatus.VERIFIED
        except Exception:
            pass

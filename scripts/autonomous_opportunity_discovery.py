#!/usr/bin/env python3
"""Mission PRODUCT-4 — Autonomous Opportunity Discovery Engine.

Removes the user as the permanent task generator by deterministically discovering
actionable next-work opportunities directly from real canonical state:
- Chief Brain (Active Goals, Open Loops, Memories, Task Continuations)
- Runtime Event Ledger & Job Results
- Existing Opportunity Queue & Claims
- Dependency Graphs & Sequenced Goals
- Gate Policies (Human, Money, Publication)
- Message Completion Stamps (OPEN, CLAIMED, DONE, NOT_DONE, HANDOFF_REQUIRED)

Key Invariants:
1. 0 Model Calls during discovery (Deterministic First).
2. Closed work stays closed unless new invalidating evidence exists.
3. No busywork / No fake activity / No mission inflation.
4. Gated branches are isolated and do not block independent safe branches.
5. Canonical deduplication across restarts and pollings.
6. Seamlessly integrates with Product-3 Cockpit and Codex Product-2C/3C/4C queues.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_json_safe(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def sha256_digest(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class CanonicalOpportunity:
    opportunity_id: str
    description: str
    target_agent: str = "antigravity"
    provider: str = "LOCAL_DETERMINISTIC"  # LOCAL_DETERMINISTIC, GOOGLE_PRO, CODEX
    status: str = "READY"  # READY, BACKLOG, ACTIVE, WAITING, HUMAN_GATE, MONEY_GATE, BLOCKED, DONE, FAILED, CIRCUIT_OPEN
    priority: int = 5
    risk: str = "LOW"  # LOW, MEDIUM, HIGH
    cost_class: str = "FREE_LOCAL"  # FREE_LOCAL, PAID
    goal_id: str = ""
    source: str = "CHIEF_BRAIN"
    source_fingerprint: str = ""
    expected_outcome: str = ""
    scope: list[str] = field(default_factory=list)
    allowed_scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    critical_path: bool = False
    parallel_safe: bool = True
    reason: str = ""
    estimated_cost: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    dedupe_hash: str = ""
    dedupe_fingerprint: str = ""
    message_stamp: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.scope and self.allowed_scope:
            self.scope = list(self.allowed_scope)
        elif self.scope and not self.allowed_scope:
            self.allowed_scope = list(self.scope)

        if not self.dedupe_hash:
            material = {
                "goal_id": self.goal_id,
                "description": self.description,
                "scope": sorted(self.scope),
                "dependencies": sorted(self.dependencies),
                "source": self.source,
            }
            self.dedupe_hash = sha256_digest(material)[:16]
        if not self.dedupe_fingerprint:
            self.dedupe_fingerprint = self.dedupe_hash

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["problem_or_goal"] = self.description
        return d


class AutonomousOpportunityDiscoveryEngine:
    """Deterministic opportunity discovery engine that evaluates canonical repo state."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.events_dir = repo_dir / "events"
        self.queue_dir = self.events_dir / "opportunity-queue"
        self.brain_dir = self.events_dir / "chief-brain"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.anomalies_dir = self.events_dir / "anomalies"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.discovered_opportunities: dict[str, CanonicalOpportunity] = {}
        self.completed_signatures: set[str] = set()
        self._load_existing_state()

    def _load_existing_state(self):
        """Loads existing opportunities and identifies closed work."""
        if self.queue_dir.exists():
            for qf in self.queue_dir.glob("*.json"):
                if qf.name.endswith(".claim.json"):
                    continue
                data = load_json_safe(qf)
                if data and isinstance(data, dict) and "opportunity_id" in data:
                    opp = CanonicalOpportunity(
                        opportunity_id=data.get("opportunity_id"),
                        description=data.get("description", data.get("problem_or_goal", "")),
                        target_agent=data.get("target_agent", "antigravity"),
                        provider=data.get("provider", "LOCAL_DETERMINISTIC"),
                        status=data.get("status", "READY"),
                        priority=data.get("priority", 5),
                        risk=data.get("risk", "LOW"),
                        cost_class=data.get("cost_class", "FREE_LOCAL"),
                        goal_id=data.get("goal_id", ""),
                        source=data.get("source", "QUEUE"),
                        source_fingerprint=data.get("source_fingerprint", ""),
                        expected_outcome=data.get("expected_outcome", ""),
                        scope=data.get("scope", data.get("allowed_scope", [])),
                        allowed_scope=data.get("allowed_scope", data.get("scope", [])),
                        dependencies=data.get("dependencies", []),
                        critical_path=data.get("critical_path", False),
                        parallel_safe=data.get("parallel_safe", True),
                        reason=data.get("reason", ""),
                        estimated_cost=data.get("estimated_cost", 0.0),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                        dedupe_hash=data.get("dedupe_hash", ""),
                        dedupe_fingerprint=data.get("dedupe_fingerprint", ""),
                        message_stamp=data.get("message_stamp"),
                    )
                    self.discovered_opportunities[opp.opportunity_id] = opp
                    if opp.status in ("DONE", "COMPLETED"):
                        self.completed_signatures.add(opp.dedupe_hash)
                        self.completed_signatures.add(opp.opportunity_id)

        # Load completed tasks from Chief Brain / Runtime / Session Controller
        if self.autonomy_dir.exists():
            curr_sess = load_json_safe(self.autonomy_dir / "current_session.json", {})
            for job_id in curr_sess.get("jobs_completed", []):
                self.completed_signatures.add(str(job_id))

            sess_state = load_json_safe(self.autonomy_dir / "session_controller_state.json", {})
            for task_id in sess_state.get("completed_tasks", []):
                self.completed_signatures.add(str(task_id))
            for fp in sess_state.get("completed_fingerprints", []):
                self.completed_signatures.add(str(fp))

        # Load memories from Chief Brain
        if self.brain_dir.exists():
            mem_file = self.brain_dir / "memories.json"
            mems = load_json_safe(mem_file, [])
            if isinstance(mems, list):
                for m in mems:
                    if isinstance(m, dict) and m.get("status") in ("RESOLVED", "DONE", "COMPLETED"):
                        mid = m.get("memory_id") or m.get("goal_id") or m.get("task_id")
                        if mid:
                            self.completed_signatures.add(str(mid))

    def evaluate_real_value_gain(
        self,
        goal_id: str,
        description: str,
        expected_outcome: str,
        trigger_reason: str,
        evidence_fingerprint: str,
        dependencies: list[str],
    ) -> tuple[bool, str]:
        """Determines whether candidate represents meaningful progress without busywork."""
        if not description or not description.strip():
            return False, "NO_GAIN: Empty description"

        # Reject busywork phrases and artificial tasks
        lower_desc = description.lower()
        busywork_patterns = [
            "routine review",
            "idle poll",
            "heartbeat tick",
            "busywork",
            "dummy test",
            "fake analytic",
            "fake revenue",
            "generate synthetic traffic",
        ]
        for pat in busywork_patterns:
            if pat in lower_desc:
                return False, f"NO_GAIN: Detected busywork pattern: {pat}"

        # Check if already completed and no invalidation evidence
        dedupe_key = sha256_digest({
            "goal_id": goal_id,
            "description": description,
            "dependencies": sorted(dependencies),
        })[:16]

        if goal_id and goal_id in self.completed_signatures and not dependencies:
            return False, "NO_GAIN: Goal already recorded as completed"

        if dedupe_key in self.completed_signatures:
            return False, "NO_GAIN: Work already completed and no invalidation evidence"

        for opp in self.discovered_opportunities.values():
            if opp.status in ("DONE", "COMPLETED"):
                if opp.dedupe_hash == dedupe_key or opp.description == description:
                    return False, "NO_GAIN: Work strand is closed"
                if goal_id and opp.goal_id == goal_id and not dependencies and not opp.dependencies:
                    return False, "NO_GAIN: Goal strand is closed"

        return True, "VALUABLE"

    def classify_gates(
        self,
        description: str,
        estimated_cost: float,
        scope: list[str],
        explicit_gate: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Classifies opportunities into appropriate gate statuses (HUMAN_GATE, MONEY_GATE, READY)."""
        if explicit_gate:
            return explicit_gate, "HIGH" if "GATE" in explicit_gate else "LOW", "FREE_LOCAL" if estimated_cost == 0.0 else "PAID"

        lower_desc = description.lower()

        # Money gate (Autonomous spend limit = 0 EUR)
        if estimated_cost > 0.0 or "purchase" in lower_desc or "credit card" in lower_desc or "subscription" in lower_desc:
            return "MONEY_GATE", "HIGH", "PAID"

        # Publication firewall / Human decision gate
        if "publish" in lower_desc or "release deployment" in lower_desc or "public upload" in lower_desc:
            return "HUMAN_GATE", "HIGH", "FREE_LOCAL"

        if "human approval" in lower_desc or "waiting for human" in lower_desc or "delete repository" in lower_desc:
            return "HUMAN_GATE", "HIGH", "FREE_LOCAL"

        return "READY", "LOW", "FREE_LOCAL"

    def classify_opportunity_value_tier(self, opp: CanonicalOpportunity) -> str:
        """Categorizes opportunities into HIGH_VALUE, USEFUL, NEUTRAL, or SUPPRESSED."""
        # 1. Suppressed checks (already completed, duplicate, or busywork)
        if opp.opportunity_id in self.completed_signatures or opp.dedupe_hash in self.completed_signatures:
            return "SUPPRESSED"

        if opp.status in ("DONE", "COMPLETED", "CIRCUIT_OPEN", "FAILED", "BLOCKED"):
            return "SUPPRESSED"

        # 2. Gates
        if opp.status in ("HUMAN_GATE", "MONEY_GATE", "WAITING"):
            return "GATED"

        # 3. HIGH_VALUE checks
        if opp.critical_path or opp.priority >= 8 or opp.provider == "LOCAL_DETERMINISTIC":
            return "HIGH_VALUE"

        # 4. USEFUL checks
        if opp.priority >= 4:
            return "USEFUL"

        return "NEUTRAL"

    def rank_opportunities(self, opportunities: list[CanonicalOpportunity]) -> list[CanonicalOpportunity]:
        """Ranks actionable opportunities deterministically: HIGH_VALUE > USEFUL > NEUTRAL."""
        tier_weights = {
            "HIGH_VALUE": 3,
            "USEFUL": 2,
            "NEUTRAL": 1,
            "GATED": 0,
            "SUPPRESSED": -1,
        }

        # Filter out suppressed
        eligible = [o for o in opportunities if self.classify_opportunity_value_tier(o) not in ("SUPPRESSED",)]

        def sort_key(o: CanonicalOpportunity):
            tier = self.classify_opportunity_value_tier(o)
            weight = tier_weights.get(tier, 0)
            return (
                weight,
                1 if o.critical_path else 0,
                o.priority,
                1 if o.status == "READY" else 0,
                -len(o.dependencies),
            )

        return sorted(eligible, key=sort_key, reverse=True)

    def discover_opportunities(
        self,
        active_goals: Optional[list[dict]] = None,
        open_loops: Optional[list[dict]] = None,
        sequenced_chains: Optional[list[dict]] = None,
        new_result: Optional[dict] = None,
    ) -> list[CanonicalOpportunity]:
        """Main entrypoint: deterministically discovers new actionable opportunities."""
        new_candidates: list[CanonicalOpportunity] = []

        # 1. Process New Incoming Results (Result -> Unblock Chain)
        if new_result and isinstance(new_result, dict):
            res_task_id = new_result.get("task_id", "")
            res_outcome = new_result.get("outcome", "")
            if res_task_id and res_outcome == "SUCCESS":
                self.completed_signatures.add(res_task_id)
                # Mark existing opportunity DONE
                if res_task_id in self.discovered_opportunities:
                    opp = self.discovered_opportunities[res_task_id]
                    opp.status = "DONE"
                    self.save_opportunity(opp)

        # 2. Process Sequenced Chains (Zero-Prompt Sequential Workflow)
        if sequenced_chains:
            for chain in sequenced_chains:
                goal_id = chain.get("goal_id", "goal-chain")
                steps = chain.get("steps", [])
                # Find first step that is not yet completed
                for step in steps:
                    step_id = step.get("step_id", "")
                    step_desc = step.get("description", "")
                    step_deps = step.get("dependencies", [])

                    # Check if step is already completed
                    if step_id in self.completed_signatures or any(o.opportunity_id == step_id and o.status == "DONE" for o in self.discovered_opportunities.values()):
                        continue

                    # Check if dependencies are all met
                    deps_satisfied = all(d in self.completed_signatures for d in step_deps)
                    if not deps_satisfied:
                        # Cannot proceed to this step yet
                        break

                    # Step is unblocked and ready!
                    is_valuable, reason = self.evaluate_real_value_gain(
                        goal_id=goal_id,
                        description=step_desc,
                        expected_outcome=step.get("expected_outcome", "Step Output"),
                        trigger_reason="SEQUENTIAL_CHAIN_UNBLOCKED",
                        evidence_fingerprint=sha256_digest(step)[:16],
                        dependencies=step_deps,
                    )
                    if not is_valuable:
                        continue

                    gate_status, risk, cost_class = self.classify_gates(
                        description=step_desc,
                        estimated_cost=step.get("estimated_cost", 0.0),
                        scope=step.get("scope", []),
                        explicit_gate=step.get("gate"),
                    )

                    opp = CanonicalOpportunity(
                        opportunity_id=step_id,
                        goal_id=goal_id,
                        description=step_desc,
                        target_agent=step.get("target_agent", "antigravity"),
                        provider=step.get("provider", "LOCAL_DETERMINISTIC"),
                        status=gate_status,
                        priority=step.get("priority", 8),
                        risk=risk,
                        cost_class=cost_class,
                        source="SEQUENCED_GOAL_CHAIN",
                        expected_outcome=step.get("expected_outcome", ""),
                        scope=step.get("scope", []),
                        dependencies=step_deps,
                        critical_path=step.get("critical_path", True),
                        parallel_safe=step.get("parallel_safe", True),
                        reason=f"Unblocked by completed dependencies: {step_deps}",
                    )
                    if self.add_opportunity(opp):
                        new_candidates.append(opp)
                    # For sequential chains, emit the first actionable step
                    break

        # 3. Process Chief Brain Active Goals
        if active_goals:
            for g in active_goals:
                if isinstance(g, str):
                    gid = g
                    gdesc = g
                    gdeps = []
                    g_exp = "Goal fulfillment"
                    g_cost = 0.0
                    g_scope = []
                    g_gate = None
                    g_fp = sha256_digest(g)[:16]
                else:
                    gid = g.get("goal_id", g.get("memory_id", ""))
                    gdesc = g.get("content", g.get("description", ""))
                    gdeps = g.get("dependencies", [])
                    g_exp = g.get("expected_outcome", "Goal fulfillment")
                    g_cost = g.get("estimated_cost", 0.0)
                    g_scope = g.get("scope", [])
                    g_gate = g.get("gate")
                    g_fp = sha256_digest(g)[:16]

                # Evaluate real value gain
                is_valuable, reason = self.evaluate_real_value_gain(
                    goal_id=gid,
                    description=gdesc,
                    expected_outcome=g_exp,
                    trigger_reason="CHIEF_BRAIN_ACTIVE_GOAL",
                    evidence_fingerprint=g_fp,
                    dependencies=gdeps,
                )
                if not is_valuable:
                    continue

                gate_status, risk, cost_class = self.classify_gates(
                    description=gdesc,
                    estimated_cost=g_cost,
                    scope=g_scope,
                    explicit_gate=g_gate,
                )

                opp_id = f"opp-goal-{sha256_digest(gid + gdesc)[:10]}"
                opp = CanonicalOpportunity(
                    opportunity_id=opp_id,
                    goal_id=gid,
                    description=gdesc,
                    target_agent=g.get("target_agent", "antigravity") if isinstance(g, dict) else "antigravity",
                    provider=g.get("provider", "LOCAL_DETERMINISTIC") if isinstance(g, dict) else "LOCAL_DETERMINISTIC",
                    status=gate_status,
                    priority=g.get("priority", 7) if isinstance(g, dict) else 7,
                    risk=risk,
                    cost_class=cost_class,
                    source="CHIEF_BRAIN_ACTIVE_GOAL",
                    expected_outcome=g_exp,
                    scope=g_scope,
                    dependencies=gdeps,
                    parallel_safe=g.get("parallel_safe", True) if isinstance(g, dict) else True,
                    reason="Discovered from active Chief Brain goal",
                )
                if self.add_opportunity(opp):
                    new_candidates.append(opp)

        # 4. Process Open Loops
        if open_loops:
            for loop in open_loops:
                lid = loop.get("loop_id", "")
                ldesc = loop.get("description", "")
                is_valuable, reason = self.evaluate_real_value_gain(
                    goal_id=loop.get("goal_id", lid),
                    description=ldesc,
                    expected_outcome="Open loop closure",
                    trigger_reason="OPEN_LOOP_CLOSURE",
                    evidence_fingerprint=sha256_digest(loop)[:16],
                    dependencies=[],
                )
                if not is_valuable:
                    continue

                gate_status, risk, cost_class = self.classify_gates(
                    description=ldesc,
                    estimated_cost=0.0,
                    scope=loop.get("scope", []),
                )

                opp_id = f"opp-loop-{sha256_digest(lid + ldesc)[:10]}"
                opp = CanonicalOpportunity(
                    opportunity_id=opp_id,
                    goal_id=loop.get("goal_id", lid),
                    description=ldesc,
                    target_agent=loop.get("target_agent", "antigravity"),
                    provider="LOCAL_DETERMINISTIC",
                    status=gate_status,
                    priority=loop.get("priority", 6),
                    risk=risk,
                    cost_class=cost_class,
                    source="CHIEF_BRAIN_OPEN_LOOP",
                    expected_outcome="Close open loop and preserve state continuity",
                    scope=loop.get("scope", []),
                    reason="Pending open loop requiring resolution",
                )
                if self.add_opportunity(opp):
                    new_candidates.append(opp)

        return new_candidates

    def add_opportunity(self, opp: CanonicalOpportunity) -> bool:
        """Adds opportunity with strict deduplication."""
        # Check against existing opportunities
        for existing in self.discovered_opportunities.values():
            if existing.dedupe_hash == opp.dedupe_hash and existing.status in ("READY", "ACTIVE", "WAITING", "DONE", "COMPLETED", "HUMAN_GATE", "MONEY_GATE"):
                return False

        if opp.dedupe_hash in self.completed_signatures:
            return False

        self.discovered_opportunities[opp.opportunity_id] = opp
        save_json_atomic(self.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())
        return True

    def save_opportunity(self, opp: CanonicalOpportunity) -> None:
        opp.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.discovered_opportunities[opp.opportunity_id] = opp
        save_json_atomic(self.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())

    def apply_message_completion_stamp(
        self,
        opportunity_id: str,
        stamp_status: str,  # OPEN, CLAIMED, DONE, NOT_DONE, HANDOFF_REQUIRED
        worker: str,
        result_ref: Optional[str] = None,
        semantic_fingerprint: Optional[str] = None,
    ) -> bool:
        """Applies a message-level completion stamp to an opportunity."""
        opp = self.discovered_opportunities.get(opportunity_id)
        if not opp:
            return False

        fp = semantic_fingerprint or opp.dedupe_fingerprint
        stamp = {
            "status": stamp_status,
            "worker": worker,
            "result_ref": result_ref,
            "semantic_fingerprint": fp,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        opp.message_stamp = stamp

        if stamp_status == "DONE":
            opp.status = "DONE"
            self.completed_signatures.add(opp.dedupe_hash)
            if fp:
                self.completed_signatures.add(fp)
        elif stamp_status in ("NOT_DONE", "HANDOFF_REQUIRED"):
            opp.status = "READY"  # Re-eligible for handoff

        self.save_opportunity(opp)
        return True

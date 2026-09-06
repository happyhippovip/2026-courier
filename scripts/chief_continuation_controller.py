#!/usr/bin/env python3
"""Fail-closed mobile command controller for the local Chief.

Only ``WEITER``, ``STATUS`` and ``STOP`` are accepted.  WEITER creates at most
one *prepared* Courier task and deliberately never invokes a provider, model,
upload, publication, payment, OAuth flow, destructive operation, or approval.
Provider chat/session history is intentionally absent from every artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

try:
    from opportunity_queue import Opportunity, OpportunityQueue
    from resource_intelligence import ResourceIntelligenceManager
    from resource_policy import ChiefContextPackageBuilder, CostGate, ResourcePolicyManager
    from review_budget import ReviewBudgetManager
except ImportError:
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.resource_intelligence import ResourceIntelligenceManager
    from scripts.resource_policy import ChiefContextPackageBuilder, CostGate, ResourcePolicyManager
    from scripts.review_budget import ReviewBudgetManager


SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
CONTINUE_ALIASES = {"WEITER", "WEITERMACHEN", "WEITER MACHEN", "FORTSETZEN", "CONTINUE"}
ALLOWED_COMMANDS = {*CONTINUE_ALIASES, "STATUS", "STOP"}
CHIEF_AUTONOMY_MODE = "ACTIVE"
MAX_AUTONOMOUS_REVIEW_SCOPE_FILES = 12
PROHIBITED_MARKERS = {
    "PUBLISH", "UPLOAD", "PUBLIC_RELEASE", "AUDIENCE", "APPROVAL", "PAYMENT",
    "PURCHASE", "SUBSCRIPTION", "CREDIT", "OAUTH", "AUTH", "DELETE", "DESTROY", "KYC",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _load(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else (default or {})
    except (OSError, ValueError):
        return default or {}


class AutonomousBacklogPlanner:
    """Derive exactly one evidence-backed, locally safe next action.

    The planner deliberately consumes only durable local files.  It never
    treats provider chat, capacity percentages from different pools, or an
    absent file as a mandate to invent work.  Its output is a *proposal* for
    the existing continuation controller; provider execution remains outside
    this local command path.
    """

    SOURCE_DIRS = (
        "events/unfinished-missions",
        "events/backlog",
        "events/ready-work",
        "events/standing-objectives",
        "events/blockers",
        "events/reviews",
    )
    TERMINAL = {"DONE", "COMPLETED", "CLOSED", "NO_VALUE", "REJECTED", "CANCELLED"}
    HUMAN_GATED = {"WAITING_FOR_HUMAN", "WAITING_HUMAN", "HUMAN_GATE_REQUIRED", "PAYMENT_APPROVAL_REQUIRED", "PUBLICATION_APPROVAL_REQUIRED"}
    BUSYWORK = ("cosmetic refactor", "format unchanged", "re-analyze unchanged", "duplicate documentation", "quota consumption")

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir

    @staticmethod
    def _text(record: dict[str, Any]) -> str:
        return " ".join(str(record.get(key, "")) for key in ("title", "description", "objective", "reason", "next_safe_action"))

    @classmethod
    def _is_busywork(cls, record: dict[str, Any]) -> bool:
        return any(marker in cls._text(record).lower() for marker in cls.BUSYWORK)

    @staticmethod
    def _iter_records(value: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        def visit(item: Any) -> None:
            if isinstance(item, list):
                for child in item:
                    visit(child)
                return
            if not isinstance(item, dict):
                return
            identity = {"task_id", "mission_id", "objective_id", "content_id", "opportunity_id"}
            if identity.intersection(item) and ({"status", "state", "action_type"}.intersection(item)):
                records.append(item)
            for child in item.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        visit(value)
        return records

    def _candidate(self, record: dict[str, Any], source: Path, category: str) -> dict[str, Any] | None:
        status = str(record.get("status", record.get("state", "UNFINISHED"))).upper()
        if status in self.TERMINAL or self._is_busywork(record):
            return None
        title = str(record.get("title") or record.get("name") or record.get("objective") or record.get("mission_id") or record.get("content_id") or record.get("task_id") or "").strip()
        reason = str(record.get("reason") or record.get("description") or record.get("next_safe_action") or record.get("action_type") or "").strip()
        if not title or not reason:
            return None
        if record.get("action_type") == "LOCAL_QC_EXECUTION":
            media_refs = [ref for ref in record.get("evidence_references", []) if isinstance(ref, str) and ref.endswith(".mp4")]
            # A QC task without a concrete readable master is not useful work;
            # leave it for a producer/blocker path instead of spending retries.
            if not media_refs or not (self.repo_dir / media_refs[0]).is_file():
                return None
        try:
            priority = int(record.get("priority", 0) or 0)
        except (TypeError, ValueError):
            priority = 0
        try:
            estimated_cost = float(record.get("estimated_cost", 0) or 0)
        except (TypeError, ValueError):
            # Malformed cost metadata is not silently treated as free.
            estimated_cost = 1.0
        category_bonus = {"INTERRUPTED": 100, "RESULT": 95, "READY": 90, "BLOCKER": 85, "REVIEW": 80, "UNFINISHED": 70, "BACKLOG": 60, "DERIVED": 50}.get(category, 0)
        risk = str(record.get("risk_class", record.get("risk", "LOW"))).upper()
        execution_class = str(record.get("execution_class", "")).upper()
        preferred_worker = str(record.get("preferred_worker_class", "")).upper()
        target = str(record.get("target_agent") or ("local" if execution_class == "DETERMINISTIC_LOCAL" or preferred_worker.startswith("LOCAL_") else "codex" if category == "REVIEW" else "antigravity")).lower()
        evidence = {"source_path": str(source.relative_to(self.repo_dir)), "source_status": status}
        for key in ("mission_id", "objective_id", "blocker_id", "source_hash", "dedupe_fingerprint"):
            if record.get(key):
                evidence[key] = record[key]
        return {
            "task_id": str(record.get("task_id") or record.get("mission_id") or "DERIVED"),
            "title": title,
            "reason": reason,
            "evidence": evidence,
            "expected_information_gain": str(record.get("expected_information_gain") or record.get("expected_value") or "Resolve current local evidence"),
            "expected_project_value": str(record.get("expected_project_value") or record.get("project_value") or "Unblocks a verified local objective"),
            "risk_class": risk if risk in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM",
            "estimated_scope": str(record.get("estimated_scope") or "SMALL"),
            "provider_suitability": target,
            "dependencies": list(record.get("dependencies") or []),
            "completion_criteria": list(record.get("completion_criteria") or ["Persist one durable local result"]),
            "human_gate": status in self.HUMAN_GATED or bool(record.get("human_gate")) or bool(record.get("requires_human")),
            "money_gate": bool(record.get("money_gate")) or estimated_cost > 0,
            "publication_gate": bool(record.get("publication_gate")) or bool(record.get("requires_external_access")) or "publish" in self._text(record).lower(),
            "status": status,
            "score": category_bonus + priority * 10 + (20 if risk == "HIGH" else 10 if risk == "MEDIUM" else 0),
            "category": category,
            "allowed_scope": list(record.get("allowed_scope") or record.get("evidence_references") or record.get("dependencies") or []),
            "allowed_actions": list(record.get("allowed_actions") or (["LOCAL_QC"] if record.get("action_type") == "LOCAL_QC_EXECUTION" else ["READ"])),
            "action_type": str(record.get("action_type") or "LOCAL_EVIDENCE_VALIDATION"),
            "evidence_references": list(record.get("evidence_references") or []),
        }

    def discover(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for rel in self.SOURCE_DIRS:
            directory = self.repo_dir / rel
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*.json")):
                payload = _load(path)
                for record in self._iter_records(payload):
                    status = str(record.get("status", record.get("state", "UNFINISHED"))).upper()
                    if rel.endswith("reviews") and status not in {"REQUIRED", "PENDING", "IMMEDIATE_REVIEW_REQUIRED", "REVIEW_REQUIRED_BEFORE_PUSH"}:
                        continue
                    category = "REVIEW" if rel.endswith("reviews") else "READY" if status in {"READY", "READY_TO_EXECUTE"} else "BLOCKER" if "BLOCK" in status else "UNFINISHED" if "MISSION" in rel.upper() else "BACKLOG"
                    candidate = self._candidate(record, path, category)
                    if candidate:
                        candidates.append(candidate)
        # Deduplicate local evidence first; same source task must not fan out.
        unique = { _digest({"title": c["title"], "evidence": c["evidence"]}): c for c in candidates }
        return sorted(unique.values(), key=lambda item: (-item["score"], item["title"]))

    def choose(self) -> dict[str, Any] | None:
        candidates = self.discover()
        # Human-gated items are intentionally returned first only when there is
        # no independent safe candidate.  A human gate never becomes authority.
        safe = [c for c in candidates if not (c["human_gate"] or c["money_gate"] or c["publication_gate"])]
        return (safe or candidates or [None])[0]


class ChiefContinuationController:
    """One bounded continuation selection, persisted for restart-safe mobile use."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.root = repo_dir / "events" / "chief-continuation"
        self.state_file = self.root / "state.json"
        self.tasks_dir = self.root / "tasks"
        self.queue = OpportunityQueue(repo_dir)
        self.resources = ResourceIntelligenceManager(repo_dir)
        self.review_budget = ReviewBudgetManager(repo_dir)
        self.planner = AutonomousBacklogPlanner(repo_dir)

    def _state(self) -> dict[str, Any]:
        return _load(self.state_file, {"schema_version": "1.0", "stopped": False, "current": None})

    def _save_state(self, state: dict[str, Any]) -> None:
        _atomic_write(self.state_file, state)

    @staticmethod
    def _human_gate_reason(opportunity: Opportunity) -> str | None:
        if not isinstance(opportunity.estimated_cost, (int, float)) or opportunity.estimated_cost != 0:
            return "PAYMENT_APPROVAL_REQUIRED"
        if opportunity.external_action_units > 0:
            return "EXTERNAL_ACTION_HUMAN_GATE_REQUIRED"
        joined = " ".join([opportunity.description, *opportunity.allowed_actions]).upper()
        if any(marker in joined for marker in PROHIBITED_MARKERS):
            return "HUMAN_GATE_REQUIRED_FOR_PROTECTED_ACTION"
        if opportunity.status == "WAITING_FOR_HUMAN":
            return "HUMAN_GATE_REQUIRED"
        return None

    @staticmethod
    def _resource_id(agent: str) -> str | None:
        normalized = agent.lower()
        if normalized.startswith("google_pro_pool_"):
            return "google_antigravity_plus"
        return {"antigravity": "google_antigravity_plus", "codex": "chatgpt_plus_codex"}.get(normalized)

    def _pool_switch_requirement(self, opportunity: Opportunity) -> dict[str, Any] | None:
        """Read pool metadata without inferring authorization or summing quota."""
        pool = str(opportunity.evidence.get("planner", {}).get("provider_pool") or opportunity.evidence.get("provider_pool") or "").upper()
        if not pool and opportunity.target_agent.upper().startswith("GOOGLE_PRO_POOL_"):
            pool = opportunity.target_agent.upper()
        if not pool:
            return None
        if pool == "GOOGLE_PRO_POOL_4":
            return {"status": "PAYMENT_APPROVAL_REQUIRED", "reason": "POOL_4_NOT_CONFIGURED", "pool": pool}
        try:
            from google_pool_controller import GooglePoolController
        except ImportError:
            from scripts.google_pool_controller import GooglePoolController
        pools = GooglePoolController(self.repo_dir).status().get("pools", {})
        current = pools.get(pool, {})
        if current.get("authorization_state") != "AUTHORIZED" or current.get("verification_state") != "VERIFIED":
            return {"status": "PROVIDER_UNAVAILABLE", "reason": "POOL_NOT_AUTHORIZED_OR_VERIFIED", "pool": pool}
        if current.get("capacity_state") not in {"EXHAUSTED", "UNAVAILABLE"}:
            return None
        alternatives = [alias for alias, row in sorted(pools.items()) if alias != pool and alias != "GOOGLE_PRO_POOL_4" and row.get("authorization_state") == "AUTHORIZED" and row.get("verification_state") == "VERIFIED" and row.get("capacity_state") == "AVAILABLE"]
        return {"status": "ACCOUNT_SWITCH_REQUIRED" if alternatives else "RESOURCE_WAIT", "reason": "CURRENT_POOL_EXHAUSTED", "pool": pool, "alternative": alternatives[0] if alternatives else None}

    def _phone_status(self, state: dict[str, Any], code: str = "STATUS") -> dict[str, Any]:
        current = state.get("current") or {}
        resource = self.resources.summary()
        return {
            "CHIEF_STATUS": code,
            "STATE": "STOPPED" if state.get("stopped") else (current.get("status") or "IDLE"),
            "CURRENT_TASK": current.get("task_id", "NONE"),
            "PROVIDER": current.get("provider", "NONE"),
            "RESOURCE_STATE": resource.get("providers", []),
            "NEXT_ACTION": current.get("next_action", "Select one safe READY action"),
            "HUMAN_GATE": current.get("human_gate", "NONE"),
            "CHIEF_AUTONOMY_MODE": CHIEF_AUTONOMY_MODE,
            "COMMAND_ACCEPTED": True,
            "model_calls": 0,
        }

    def handle(self, command: str) -> dict[str, Any]:
        raw_command = command.strip() if isinstance(command, str) else ""
        try:
            from chief_autopilot import BoundedChiefAutopilot, parse_autopilot_command
        except ImportError:
            from scripts.chief_autopilot import BoundedChiefAutopilot, parse_autopilot_command
        if parse_autopilot_command(raw_command) is not None:
            autopilot = BoundedChiefAutopilot(self.repo_dir)
            started = autopilot.start(raw_command)
            if started.get("CHIEF_STATUS") == "AUTOPILOT_STARTED":
                started["first_local_cycle"] = autopilot.run_available()
            return started
        normalized = raw_command.upper()
        if normalized in CONTINUE_ALIASES:
            normalized = "WEITER"
        if normalized not in ALLOWED_COMMANDS:
            return {"CHIEF_STATUS": "REJECTED", "STATE": "UNKNOWN_COMMAND", "COMMAND_ACCEPTED": False,
                    "reason": "ONLY_WEITER_STATUS_STOP_SUPPORTED", "model_calls": 0}
        state = self._state()
        if normalized == "STATUS":
            response = self._phone_status(state)
            response["AUTOPILOT"] = BoundedChiefAutopilot(self.repo_dir).lease()
            return response
        if normalized == "STOP":
            state["stopped"] = True
            state["stop_reason"] = "EXPLICIT_HUMAN_STOP"
            self._save_state(state)
            response = self._phone_status(state, "STOP_ACCEPTED")
            response["AUTOPILOT"] = BoundedChiefAutopilot(self.repo_dir).stop()
            return response
        return self._continue(state)

    def _ingest_current_result(self, state: dict[str, Any], current: dict[str, Any], result: Path) -> None:
        """Finalize only the claimed opportunity tied to a durable task result."""
        current["status"] = "RESULT_INGESTED"
        current["result_ref"] = str(result.relative_to(self.repo_dir))
        current["next_action"] = "Select one new safe local action on the next WEITER"
        opportunity_id = current.get("opportunity_id")
        if isinstance(opportunity_id, str):
            opportunity = self.queue.get_opportunity(opportunity_id)
            if opportunity and opportunity.status == "RUNNING":
                opportunity.status = "COMPLETED"
                self.queue.save_opportunity(opportunity)
            claim_id = current.get("claim_id")
            if isinstance(claim_id, str):
                self.queue.release_opportunity_claim(opportunity_id, claim_id)
        state["last_result"] = {"task_id": current.get("task_id"), "result_ref": current["result_ref"]}
        state["current"] = None
        self._save_state(state)

    @staticmethod
    def _opportunity_from_plan(plan: dict[str, Any]) -> Opportunity:
        fingerprint = _digest({"title": plan["title"], "evidence": plan["evidence"], "reason": plan["reason"]})
        return Opportunity(
            opportunity_id=f"OPP-AUTONOMOUS-{fingerprint[:16]}", source="AUTONOMOUS_BACKLOG_PLANNER",
            objective_id=str(plan["evidence"].get("objective_id") or plan["task_id"]), project="2026-courier",
            description=plan["reason"], priority=max(1, min(10, int(plan["score"] // 10))),
            expected_value=plan["expected_project_value"], evidence={**plan["evidence"], "planner": plan},
            risk=plan["risk_class"], risk_class=plan["risk_class"], estimated_cost=1.0 if plan["money_gate"] else 0.0,
            external_action_units=1 if plan["publication_gate"] else 0, heavy_job=True,
            target_agent=plan["provider_suitability"], allowed_scope=plan["allowed_scope"],
            allowed_actions=plan["allowed_actions"], status="WAITING_FOR_HUMAN" if plan["human_gate"] else "READY",
        )

    def _derive_opportunity(self) -> tuple[Opportunity | None, dict[str, Any] | None]:
        # A high-risk local delta is canonical evidence for a bounded review
        # proposal.  This evaluates no provider and deliberately does not turn
        # ordinary unchanged work into a recurring review task.
        changed_files: list[str] = []
        dirty_entries: list[str] = []
        diff_text = ""
        try:
            status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo_dir, capture_output=True, text=True, timeout=5)
            if status.returncode == 0:
                dirty_entries = [line for line in status.stdout.splitlines() if len(line) > 3 and line[:2] != "!!"]
                diff = subprocess.run(["git", "diff", "--"], cwd=self.repo_dir, capture_output=True, text=True, timeout=10)
                if diff.returncode == 0:
                    diff_text = diff.stdout
                names = subprocess.run(["git", "diff", "--name-only", "--"], cwd=self.repo_dir, capture_output=True, text=True, timeout=5)
                if names.returncode == 0:
                    changed_files = [line for line in names.stdout.splitlines() if line]
        except (OSError, subprocess.SubprocessError):
            pass
        review = self.review_budget.evaluate_review_requirement(changed_files=changed_files, diff_str=diff_text)
        # A shared or oversized worktree cannot truthfully be represented as a
        # compact autonomous delta review.  An explicit review artifact may
        # still be discovered by the planner, but automatic scope capture must
        # fail closed rather than consume another worker's active delta.
        compact_owned_delta = bool(changed_files) and len(changed_files) <= MAX_AUTONOMOUS_REVIEW_SCOPE_FILES and len(dirty_entries) <= MAX_AUTONOMOUS_REVIEW_SCOPE_FILES
        if review["decision"] == "IMMEDIATE_REVIEW_REQUIRED" and compact_owned_delta:
            review_task_fingerprint = _digest({"files": changed_files, "diff": diff_text})
            plan = {
                "task_id": f"REVIEW-{review_task_fingerprint[:16]}",
                "title": "Independent bounded review of current high-risk local delta",
                "reason": review["reason"],
                "evidence": {"changed_files": changed_files, "review_fingerprint": review["review_fingerprint"]},
                "expected_information_gain": "Confirm the high-risk local delta before activation or release",
                "expected_project_value": "Preserve safety at the active trust boundary",
                "risk_class": "HIGH", "estimated_scope": "SMALL", "provider_suitability": "codex",
                "dependencies": [], "completion_criteria": ["Independent delta review is recorded"],
                "human_gate": False, "money_gate": False, "publication_gate": False, "status": "REQUIRED",
                "score": 900, "category": "REVIEW", "allowed_scope": changed_files, "allowed_actions": ["READ", "TEST"],
            }
        else:
            plan = self.planner.choose()
        if not plan:
            return None, None
        opportunity = self._opportunity_from_plan(plan)
        existing = self.queue.get_opportunity(opportunity.opportunity_id)
        if existing:
            return existing, plan
        # Atomic queue insertion retains the planner fingerprint across restart.
        self.queue.add_opportunity(opportunity)
        self.queue = OpportunityQueue(self.repo_dir)
        return self.queue.get_opportunity(opportunity.opportunity_id), plan

    def _continue(self, state: dict[str, Any]) -> dict[str, Any]:
        # Canonical queue files win over a stale controller instance after a
        # restart or a mobile WEITER arriving after another local writer.
        self.queue = OpportunityQueue(self.repo_dir)
        if state.get("stopped"):
            return self._phone_status(state, "STOPPED_NO_NEW_DISPATCH")
        switch_state = _load(self.repo_dir / "events" / "resource-intelligence" / "google_pool_switch_state.json")
        if switch_state.get("state") == "HUMAN_AUTH_REQUIRED":
            response = self._phone_status(state, "ACCOUNT_SWITCH_REQUIRED")
            response.update({
                "CURRENT_PROVIDER_POOL": switch_state.get("from_pool", "UNKNOWN"),
                "RECOMMENDED_PROVIDER_POOL": switch_state.get("to_pool", "UNKNOWN"),
                "WORK_CHECKPOINTED": bool(switch_state.get("checkpoint")),
                "SAFE_TO_SWITCH": True,
            })
            return response
        current = state.get("current") or {}
        scope_files = current.get("context_package", {}).get("scope_files", []) if isinstance(current.get("context_package"), dict) else []
        planner_category = current.get("planner_metadata", {}).get("category") if isinstance(current.get("planner_metadata"), dict) else None
        if current.get("status") == "PREPARED_NOT_EXECUTED" and planner_category == "REVIEW" and len(scope_files) > MAX_AUTONOMOUS_REVIEW_SCOPE_FILES:
            # Never allow a purportedly bounded autonomous review to consume a
            # parallel worker's broad dirty worktree.  Keep durable evidence of
            # the refusal and do not silently retry the same oversized task.
            opportunity_id = current.get("opportunity_id")
            if isinstance(opportunity_id, str):
                opportunity = self.queue.get_opportunity(opportunity_id)
                if opportunity:
                    opportunity.status = "BLOCKED"
                    self.queue.save_opportunity(opportunity)
                    claim_id = current.get("claim_id")
                    if isinstance(claim_id, str):
                        self.queue.release_opportunity_claim(opportunity_id, claim_id)
            state["last_blocked"] = {"task_id": current.get("task_id"), "reason": "REVIEW_SCOPE_EXCEEDS_AUTONOMOUS_BOUND", "scope_count": len(scope_files)}
            state["current"] = None
            self._save_state(state)
            self.queue = OpportunityQueue(self.repo_dir)
            current = {}
        if current.get("status") in {"PREPARED_NOT_EXECUTED", "RUNNING", "WAITING_FOR_RESULT"}:
            # Provider/chat sessions are not trusted state.  Only a durable
            # Courier result bearing this exact task ID can advance the cursor.
            result_files = (self.repo_dir / "events" / "processed").glob("*.json")
            result = next((path for path in result_files if _load(path).get("task_id") == current.get("task_id")), None)
            if result is not None:
                self._ingest_current_result(state, current, result)
            else:
                return self._phone_status(state, "ALREADY_RUNNING")

        # Gate the highest-value READY candidate before queue filtering can hide
        # an unsafe cost/publication request as merely "no work".
        ready_candidates = self.queue.list_opportunities(status="READY")
        candidate = ready_candidates[0] if ready_candidates else None
        if candidate:
            candidate_gate = self._human_gate_reason(candidate)
            if candidate_gate:
                state["current"] = {"status": "WAITING_FOR_HUMAN", "human_gate": candidate_gate, "next_action": "Await explicit human decision"}
                self._save_state(state)
                return self._phone_status(state, "HUMAN_GATE_REQUIRED")

        opportunity = self.queue.select_next_opportunity()
        planner_metadata: dict[str, Any] | None = None
        if not opportunity:
            opportunity, planner_metadata = self._derive_opportunity()
            if opportunity and (planner_metadata or {}).get("human_gate"):
                state["current"] = {"status": "WAITING_FOR_HUMAN", "human_gate": "HUMAN_GATE_REQUIRED", "next_action": "Await one explicit human decision"}
                self._save_state(state)
                response = self._phone_status(state, "HUMAN_GATE_REQUIRED")
                response.update({"GATE_TYPE": "HUMAN_GATE_REQUIRED", "WHY_REQUIRED": planner_metadata["reason"], "ONE_REQUIRED_HUMAN_ACTION": "Approve the protected action explicitly"})
                return response
        if not opportunity:
            return {**self._phone_status(state, "NO_READY_ACTION"), "STATE": "IDLE", "NEXT_ACTION": "Await new local evidence", "REASON": "NO_SAFE_CANONICAL_LOCAL_WORK_FOUND", "EVIDENCE": "No interrupted task, result, ready item, backlog, or derivable local mission"}

        gate = self._human_gate_reason(opportunity)
        if gate:
            state["current"] = {"status": "WAITING_FOR_HUMAN", "human_gate": gate, "next_action": "Await explicit human decision"}
            self._save_state(state)
            return self._phone_status(state, "HUMAN_GATE_REQUIRED")

        resource_id = self._resource_id(opportunity.target_agent)
        if not resource_id or not ResourcePolicyManager.is_resource_allowed(resource_id, self.repo_dir):
            return {**self._phone_status(state, "PROVIDER_UNAVAILABLE"), "STATE": "BLOCKED", "HUMAN_GATE": "NONE"}
        pool_requirement = self._pool_switch_requirement(opportunity)
        if pool_requirement and pool_requirement["status"] in {"PAYMENT_APPROVAL_REQUIRED", "PROVIDER_UNAVAILABLE", "RESOURCE_WAIT"}:
            response = self._phone_status(state, "HUMAN_GATE_REQUIRED" if pool_requirement["status"] == "PAYMENT_APPROVAL_REQUIRED" else pool_requirement["status"])
            response.update({"STATE": "BLOCKED", "HUMAN_GATE": pool_requirement["status"] if pool_requirement["status"] == "PAYMENT_APPROVAL_REQUIRED" else "NONE", "REASON": pool_requirement["reason"]})
            return response
        cost = CostGate.evaluate_spend_request(resource_id, 0.0, "PREPARE_BOUNDED_TASK", self.repo_dir)
        if not cost.get("allowed"):
            return {**self._phone_status(state, "HUMAN_GATE_REQUIRED"), "STATE": "BLOCKED", "HUMAN_GATE": cost.get("reason")}

        state_fingerprint = _digest({"opportunity": opportunity.to_dict(), "resource": self.resources.summary()})
        workflow_id = f"WF-WEITER-{state_fingerprint[:12]}"
        task_id = f"TASK-WEITER-{state_fingerprint[:16]}"
        task_path = self.tasks_dir / f"{task_id}.json"
        if task_path.exists():
            state["current"] = _load(task_path)
            self._save_state(state)
            return self._phone_status(state, "ALREADY_RUNNING")

        claimed, claim_code, claim = self.queue.claim_opportunity(opportunity.opportunity_id, claim_owner=task_id)
        if not claimed:
            return {**self._phone_status(state, "ALREADY_RUNNING"), "STATE": "WAITING_FOR_RESULT", "NEXT_ACTION": claim_code}

        review = self.review_budget.evaluate_review_requirement(changed_files=[], diff_str="")
        context = ChiefContextPackageBuilder.build_compact_package(
            workflow_id=workflow_id, task_id=task_id, instruction=opportunity.description,
            scope_files=opportunity.allowed_scope, context_version=1,
            context_delta={"opportunity_id": opportunity.opportunity_id, "resource": self.resources.context_for_role("ROUTER")},
            repo_dir=self.repo_dir,
        )
        task = {
            "schema_version": "1.0", "task_id": task_id, "workflow_id": workflow_id,
            "correlation_id": f"corr-{state_fingerprint[:20]}", "opportunity_id": opportunity.opportunity_id,
            "provider": resource_id, "target_agent": opportunity.target_agent,
            "status": "PREPARED_NOT_EXECUTED", "next_action": "Wait for a separately authorized provider/worker result",
            "human_gate": "NONE", "claim_id": claim.get("claim_id"), "state_fingerprint": state_fingerprint,
            "context_package": context, "review_policy": {"decision": review["decision"], "reason": review["reason"]},
            "planner_metadata": planner_metadata or opportunity.evidence.get("planner", {}),
            "provider_chat_history_included": False, "external_actions": 0, "model_calls": 0,
            "max_iterations": 1, "dispatch_mode": "PREPARED_LOCAL_ONLY",
        }
        _atomic_write(task_path, task)
        state["current"] = task
        self._save_state(state)
        if pool_requirement and pool_requirement["status"] == "ACCOUNT_SWITCH_REQUIRED":
            try:
                from google_pool_controller import GooglePoolController
            except ImportError:
                from scripts.google_pool_controller import GooglePoolController
            prepared = GooglePoolController(self.repo_dir).prepare_switch(pool_requirement["pool"], pool_requirement["alternative"], task_id)
            if prepared.get("status") == "SAFE_TO_SWITCH":
                response = self._phone_status(state, "ACCOUNT_SWITCH_REQUIRED")
                response.update({"CURRENT_PROVIDER_POOL": pool_requirement["pool"], "RECOMMENDED_PROVIDER_POOL": pool_requirement["alternative"], "WORK_CHECKPOINTED": True, "SAFE_TO_SWITCH": True})
                return response
        return self._phone_status(state, "WEITER_ACCEPTED")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Fail-closed local Chief continuation command")
    parser.add_argument("command", help="WEITER/WEITERMACHEN/FORTSETZEN/CONTINUE, STATUS, or STOP")
    args = parser.parse_args()
    print(json.dumps(ChiefContinuationController().handle(args.command), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

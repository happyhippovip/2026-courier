#!/usr/bin/env python3
"""Canonical Persistent Chief Brain / Zero-Handover Operating System (Mission 169).

The local Chief Brain is the single source of truth for durable human intent,
project goals, active rules, open loops, task continuation, result ingestion,
and provider-neutral task routing.

Chats and AI provider contexts are replaceable workers; they are NEVER the source of truth.

Key Architectural Guarantees:
- Durable User Intent: "Remember until I change it" (explicit supersession, no silent expiry).
- Zero-Handover Startup: Compact CHIEF_BOOTSTRAP_CONTEXT reconstructs complete state.
- Automatic Context Resolver: Builds bounded, relevant CHIEF_CONTEXT_PACKAGE without chat dumps.
- Strict Governance & Firewalls:
  - AUTONOMOUS_SPEND_LIMIT = 0 EUR (CostGate / PAYMENT_APPROVAL_REQUIRED)
  - PUBLICATION_AUTHORIZATION_INFERENCE = DENY
  - SECRET_STORAGE = DENY (passwords, tokens, credentials rejected fail-closed)
  - AUTO_ACCOUNT_LOGIN = DENY, AUTO_ACCOUNT_ROTATION = DENY
  - PHYSICAL_NODE_B_USED = NO
- Worker Claim vs Deterministic Evidence: Strictly separated during result ingestion.
- Deterministic Open-Loop & "What Next?" Engines.
- Atomic Persistence & Compaction: Hot / Warm / Archive tiering without data loss.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
BRAIN_DIR = EVENTS_DIR / "chief-brain"
SCHEMAS_DIR = COURIER_DIR / "schemas"

# Prohibited Secret & Sensitive Patterns
SECRET_PATTERNS = [
    re.compile(r"(?i)(password|secret|apikey|api_key|token|auth|bearer)[\s:=]+[\"\x27][A-Za-z0-9_\-\.]{12,}[\"\x27]"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
]

# Sensitive Action Markers requiring explicit human approval
HIGH_IMPACT_MARKERS = {
    "PUBLICATION_AUTHORIZATION", "PAYMENT_AUTHORIZATION", "CREDIT_CARD",
    "PURCHASE", "SUBSCRIPTION", "DELETE_REPOSITORY", "DISABLE_SECURITY",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json_safe(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def scan_for_forbidden_secrets(text_or_obj: Any) -> List[str]:
    text = json.dumps(text_or_obj) if not isinstance(text_or_obj, str) else text_or_obj
    matches = []
    for pat in SECRET_PATTERNS:
        m = pat.findall(text)
        if m:
            matches.extend([str(item) for item in m])
    return matches


# ==============================================================================
# Brain Memory Models
# ==============================================================================

VALID_ITEM_TYPES = {
    "USER_INTENT",
    "VERIFIED_CURRENT",
    "HISTORICAL_DECISION",
    "ACTIVE_GOAL",
    "ACTIVE_TASK",
    "OPEN_LOOP",
    "BLOCKER",
    "HUMAN_GATE",
    "PROVIDER_RESULT",
    "RESOURCE_STATE",
    "PROJECT_RULE",
    "SECURITY_BOUNDARY",
    "SUPERSEDED",
    "REJECTED",
    "COMPLETED",
    "UNKNOWN",
}

VALID_STATUSES = {"ACTIVE", "SUPERSEDED", "REJECTED", "COMPLETED", "UNKNOWN", "TOMBSTONE"}
VALID_CONFIDENCES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    item_type: str
    content: str
    summary: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = "ACTIVE"
    scope: str = "PROJECT_GLOBAL"
    source: str = "HUMAN_EXPLICIT"
    confidence: str = "HIGH"
    evidence_refs: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    related_task_ids: list[str] = field(default_factory=list)
    related_project: str = "2026-courier"
    last_verified_at: str = ""
    canonical_digest: str = ""

    def __post_init__(self) -> None:
        if not self.memory_id.strip():
            raise ValueError("memory_id is required")
        if self.item_type not in VALID_ITEM_TYPES:
            raise ValueError(f"Invalid item_type: {self.item_type}")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.confidence not in VALID_CONFIDENCES:
            raise ValueError(f"Invalid confidence: {self.confidence}")

        # Scan for forbidden secrets fail-closed
        secrets = scan_for_forbidden_secrets(self.content)
        if secrets:
            raise ValueError(f"CRITICAL: Secret pattern detected in MemoryItem: {secrets}")

        now = utc_now()
        if not self.created_at:
            object.__setattr__(self, "created_at", now)
        if not self.updated_at:
            object.__setattr__(self, "updated_at", now)
        if not self.last_verified_at:
            object.__setattr__(self, "last_verified_at", now)
        if not self.summary:
            object.__setattr__(self, "summary", self.content[:120].strip())

        if not self.canonical_digest:
            material = {
                "memory_id": self.memory_id,
                "item_type": self.item_type,
                "content": self.content,
                "scope": self.scope,
                "source": self.source,
            }
            object.__setattr__(self, "canonical_digest", sha256_digest(material))


@dataclass(frozen=True)
class IdeaItem:
    idea_id: str
    raw_intent: str
    normalized_interpretation: str
    tags: list[str] = field(default_factory=list)
    state: str = "NEW"  # NEW, CLARIFIED, PLANNED, ACTIVE, DEFERRED, REJECTED, COMPLETED, SUPERSEDED
    created_at: str = ""
    updated_at: str = ""
    planned_goal_id: Optional[str] = None
    superseded_by: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.idea_id.strip():
            raise ValueError("idea_id is required")
        if not self.raw_intent.strip():
            raise ValueError("raw_intent is required")
        secrets = scan_for_forbidden_secrets(self.raw_intent)
        if secrets:
            raise ValueError(f"CRITICAL: Secret pattern in IdeaItem: {secrets}")
        now = utc_now()
        if not self.created_at:
            object.__setattr__(self, "created_at", now)
        if not self.updated_at:
            object.__setattr__(self, "updated_at", now)


@dataclass(frozen=True)
class TaskContinuationState:
    task_id: str
    goal_id: str
    state: str  # READY, RUNNING, VERIFYING, BLOCKED, HUMAN_GATE, FAILED, COMPLETED, PAUSED, HUNG, UNKNOWN
    worker: str
    mission_id: str = ""
    started_at: str = ""
    last_progress_at: str = ""
    result_id: Optional[str] = None
    blocked_reason: Optional[str] = None
    human_gate: Optional[str] = None
    next_action: str = ""
    resume_token: str = ""
    affected_files: list[str] = field(default_factory=list)
    verification_state: str = "UNVERIFIED"

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id is required")


# ==============================================================================
# Chief Brain Engine
# ==============================================================================

class ChiefBrain:
    """Canonical persistent memory store and zero-handover controller."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.brain_dir = repo_dir / "events" / "chief-brain"
        self.memories_file = self.brain_dir / "memories.json"
        self.ideas_file = self.brain_dir / "idea_inbox.json"
        self.tasks_file = self.brain_dir / "tasks_continuation.json"
        self.open_loops_file = self.brain_dir / "open_loops.json"
        self.status_file = self.brain_dir / "status.json"
        self.archive_dir = self.brain_dir / "archive"

        # Governance & Firewall invariants
        self.AUTONOMOUS_SPEND_LIMIT_EUR: float = 0.0
        self.PAYMENT_APPROVAL_REQUIRED: bool = True
        self.PUBLICATION_AUTHORIZATION_INFERENCE: str = "DENY"
        self.SECRET_STORAGE: str = "DENY"
        self.AUTO_ACCOUNT_LOGIN: str = "DENY"
        self.AUTO_ACCOUNT_ROTATION: str = "DENY"
        self.PHYSICAL_NODE_B_USED: str = "NO"

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Storage IO
    # --------------------------------------------------------------------------

    def _load_memories(self) -> Dict[str, dict]:
        data = read_json_safe(self.memories_file, {})
        return data if isinstance(data, dict) else {}

    def _save_memories(self, memories: Dict[str, dict]) -> None:
        atomic_write_json(self.memories_file, memories)

    def _load_ideas(self) -> Dict[str, dict]:
        data = read_json_safe(self.ideas_file, {})
        return data if isinstance(data, dict) else {}

    def _save_ideas(self, ideas: Dict[str, dict]) -> None:
        atomic_write_json(self.ideas_file, ideas)

    def _load_tasks(self) -> Dict[str, dict]:
        data = read_json_safe(self.tasks_file, {})
        return data if isinstance(data, dict) else {}

    def _save_tasks(self, tasks: Dict[str, dict]) -> None:
        atomic_write_json(self.tasks_file, tasks)

    # --------------------------------------------------------------------------
    # Phase B & C: Durable User Intent & Memory Storage
    # --------------------------------------------------------------------------

    def record_memory(self, item: MemoryItem) -> MemoryItem:
        """Saves a durable memory item to the canonical store."""
        # Governance gate: worker cannot silently grant publication or payment
        if item.source == "WORKER_RESULT":
            for marker in HIGH_IMPACT_MARKERS:
                if marker in item.content.upper():
                    raise PermissionError(f"Workers cannot create high-impact governance memory: {marker}")

        memories = self._load_memories()
        memories[item.memory_id] = asdict(item)
        self._save_memories(memories)
        self._update_open_loops()
        return item

    def record_user_intent(
        self,
        raw_text: str,
        scope: str = "PROJECT_GLOBAL",
        supersedes_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryItem:
        """Durable intent semantics: preserved until explicitly superseded or completed."""
        # Check duplicate or conflict relations
        relation = self.detect_intent_relation(raw_text)
        if relation.get("relation") == "SAME_INTENT" and not supersedes_id:
            existing_id = relation.get("existing_memory_id")
            if existing_id:
                memories = self._load_memories()
                if existing_id in memories:
                    # Update verification timestamp on existing intent without duplicate creation
                    m = memories[existing_id]
                    m["last_verified_at"] = utc_now()
                    self._save_memories(memories)
                    return MemoryItem(**m)

        memory_id = f"intent-{uuid.uuid4().hex[:12]}"
        item = MemoryItem(
            memory_id=memory_id,
            item_type="USER_INTENT",
            content=raw_text.strip(),
            summary=raw_text[:100].strip(),
            scope=scope,
            source="HUMAN_EXPLICIT",
            confidence="HIGH",
            supersedes=supersedes_id,
        )

        if supersedes_id:
            self.supersede_memory(supersedes_id, memory_id, reason="Superseded by newer human intent")

        return self.record_memory(item)

    def supersede_memory(self, old_memory_id: str, new_memory_id: str, reason: str = "") -> None:
        """Auditable supersession: marks old memory as SUPERSEDED with link to new."""
        memories = self._load_memories()
        if old_memory_id in memories:
            old_item = memories[old_memory_id]
            old_item["status"] = "SUPERSEDED"
            old_item["superseded_by"] = new_memory_id
            old_item["updated_at"] = utc_now()
            self._save_memories(memories)

    def tombstone_memory(self, memory_id: str, reason: str = "Explicit human removal") -> None:
        """Auditable tombstone for forgotten memories."""
        memories = self._load_memories()
        if memory_id in memories:
            item = memories[memory_id]
            item["status"] = "TOMBSTONE"
            item["updated_at"] = utc_now()
            item["content"] = f"[TOMBSTONE] {reason} (Archived at {utc_now()})"
            self._save_memories(memories)

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        memories = self._load_memories()
        data = memories.get(memory_id)
        return MemoryItem(**data) if data else None

    def query_memories(
        self,
        item_type: Optional[str] = None,
        status: Optional[str] = "ACTIVE",
        scope: Optional[str] = None,
    ) -> List[MemoryItem]:
        memories = self._load_memories()
        results = []
        for data in memories.values():
            if item_type and data.get("item_type") != item_type:
                continue
            if status and data.get("status") != status:
                continue
            if scope and data.get("scope") != scope:
                continue
            results.append(MemoryItem(**data))
        return sorted(results, key=lambda m: m.created_at)

    # --------------------------------------------------------------------------
    # Phase K & Q: Idea Inbox & Duplicate Handling
    # --------------------------------------------------------------------------

    def record_idea(self, raw_intent: str, tags: Optional[List[str]] = None) -> IdeaItem:
        """Stores rough ideas in durable idea inbox."""
        idea_id = f"idea-{uuid.uuid4().hex[:10]}"
        # Normalize interpretation
        normalized = re.sub(r"\s+", " ", raw_intent.strip())
        idea = IdeaItem(
            idea_id=idea_id,
            raw_intent=raw_intent.strip(),
            normalized_interpretation=normalized,
            tags=tags or [],
            state="NEW",
        )
        ideas = self._load_ideas()
        ideas[idea_id] = asdict(idea)
        self._save_ideas(ideas)
        self._update_open_loops()
        return idea

    def detect_intent_relation(self, new_text: str) -> Dict[str, Any]:
        """Detects if new intent is duplicate, conflict, or extension of existing active intent."""
        norm_new = re.sub(r"\s+", " ", new_text.lower().strip())
        memories = self._load_memories()

        for mid, mdata in memories.items():
            if mdata.get("item_type") == "USER_INTENT" and mdata.get("status") == "ACTIVE":
                existing_norm = re.sub(r"\s+", " ", mdata.get("content", "").lower().strip())
                if norm_new == existing_norm:
                    return {"relation": "SAME_INTENT", "existing_memory_id": mid}
                if norm_new in existing_norm or existing_norm in norm_new:
                    return {"relation": "EXTENSION", "existing_memory_id": mid}

        return {"relation": "NEW_INTENT", "existing_memory_id": None}

    # --------------------------------------------------------------------------
    # Phase E: Continuation State & Open Loops
    # --------------------------------------------------------------------------

    def record_task_state(self, task: TaskContinuationState) -> TaskContinuationState:
        tasks = self._load_tasks()
        tasks[task.task_id] = asdict(task)
        self._save_tasks(tasks)
        self._update_open_loops()
        return task

    def get_task_state(self, task_id: str) -> Optional[TaskContinuationState]:
        tasks = self._load_tasks()
        data = tasks.get(task_id)
        return TaskContinuationState(**data) if data else None

    def list_tasks(self, state: Optional[str] = None) -> List[TaskContinuationState]:
        tasks = self._load_tasks()
        results = []
        for t in tasks.values():
            if state and t.get("state") != state:
                continue
            results.append(TaskContinuationState(**t))
        return sorted(results, key=lambda t: t.started_at)

    def _update_open_loops(self) -> List[Dict[str, Any]]:
        """Maintains deterministic open loop index from durable event state."""
        loops: List[Dict[str, Any]] = []

        # 1. Unresolved running tasks
        tasks = self._load_tasks()
        for tid, tdata in tasks.items():
            st = tdata.get("state", "UNKNOWN")
            if st in ("RUNNING", "READY", "VERIFYING"):
                loops.append({
                    "loop_id": f"loop-task-{tid}",
                    "loop_type": "UNRESOLVED_TASK",
                    "task_id": tid,
                    "goal_id": tdata.get("goal_id"),
                    "state": st,
                    "reason": f"Task {tid} in state {st}",
                })
            elif st == "BLOCKED":
                loops.append({
                    "loop_id": f"loop-blocked-{tid}",
                    "loop_type": "KNOWN_BLOCKER",
                    "task_id": tid,
                    "reason": tdata.get("blocked_reason") or "Blocked without explicit reason",
                })
            elif st == "HUMAN_GATE":
                loops.append({
                    "loop_id": f"loop-human-gate-{tid}",
                    "loop_type": "HUMAN_GATE_PENDING",
                    "task_id": tid,
                    "reason": tdata.get("human_gate") or "Human gate pending",
                })
            elif st == "FAILED":
                loops.append({
                    "loop_id": f"loop-failed-{tid}",
                    "loop_type": "RETRY_DECISION_PENDING",
                    "task_id": tid,
                    "reason": "Task failed and awaits retry or closure",
                })

        # 2. Ideas pending planning
        ideas = self._load_ideas()
        for iid, idata in ideas.items():
            if idata.get("state") == "NEW":
                loops.append({
                    "loop_id": f"loop-idea-{iid}",
                    "loop_type": "UNPLANNED_IDEA",
                    "idea_id": iid,
                    "summary": idata.get("normalized_interpretation", "")[:80],
                })

        atomic_write_json(self.open_loops_file, loops)
        return loops

    def get_open_loops(self) -> List[Dict[str, Any]]:
        data = read_json_safe(self.open_loops_file, [])
        return data if isinstance(data, list) else []

    # --------------------------------------------------------------------------
    # Phase F: Worker Result Ingestion
    # --------------------------------------------------------------------------

    def ingest_worker_result(
        self,
        task_id: str,
        worker: str,
        outcome: str,  # SUCCESS, FAIL, BLOCKED, REVIEW_REQUIRED
        evidence: Dict[str, Any],
        files_changed: Optional[List[str]] = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        claims: Optional[Dict[str, Any]] = None,
        verified_by_chief: bool = False,
    ) -> Dict[str, Any]:
        """Ingests worker final report into local canonical brain, keeping claims separate from deterministic evidence."""
        result_id = f"res-{uuid.uuid4().hex[:12]}"
        files = files_changed or []

        # Create provider result memory record
        content_obj = {
            "task_id": task_id,
            "worker": worker,
            "outcome": outcome,
            "worker_claims": claims or {},
            "deterministic_evidence": evidence,
            "files_changed": files,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "verified_by_chief": verified_by_chief,
        }

        mem = MemoryItem(
            memory_id=result_id,
            item_type="PROVIDER_RESULT",
            content=canonical_json(content_obj),
            summary=f"Result for task {task_id} from {worker}: {outcome}",
            source="WORKER_RESULT",
            confidence="HIGH" if verified_by_chief else "MEDIUM",
            related_task_ids=[task_id],
        )
        self.record_memory(mem)

        # Update task continuation state
        current_task = self.get_task_state(task_id)
        if current_task:
            new_state = "COMPLETED" if outcome == "SUCCESS" else ("FAILED" if outcome == "FAIL" else "BLOCKED")
            updated = TaskContinuationState(
                task_id=task_id,
                goal_id=current_task.goal_id,
                state=new_state,
                worker=worker,
                mission_id=current_task.mission_id,
                started_at=current_task.started_at,
                last_progress_at=utc_now(),
                result_id=result_id,
                affected_files=files,
                verification_state="VERIFIED" if verified_by_chief else "WORKER_CLAIM_UNVERIFIED",
                next_action="Review completed task or continue to next backlog item" if outcome == "SUCCESS" else "Address failure or blocker",
            )
            self.record_task_state(updated)

        return {"result_id": result_id, "status": "INGESTED", "outcome": outcome}

    # --------------------------------------------------------------------------
    # Phase D: Context Resolver (CHIEF_CONTEXT_PACKAGE)
    # --------------------------------------------------------------------------

    def build_context_package(
        self,
        task_id: str,
        provider_role: str = "GOOGLE_BUILD",
        mission: str = "Mission Autonomous Work",
        scope_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Constructs compact schema-validated worker context package omitting chat dumps."""
        files = scope_files or []
        active_goals = self.query_memories(item_type="ACTIVE_GOAL")
        active_rules = self.query_memories(item_type="PROJECT_RULE")
        open_loops = self.get_open_loops()

        # Build file manifest
        manifest = {}
        for rel in files:
            p = self.repo_dir / rel
            if p.is_file():
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                manifest[rel] = h

        # Fetch recent relevant results
        recent_results = [m.content for m in self.query_memories(item_type="PROVIDER_RESULT")[-3:]]

        context_id = f"ctx-{uuid.uuid4().hex[:12]}"
        package = {
            "schema_version": "CHIEF_CONTEXT_PACKAGE_V1",
            "context_package_id": context_id,
            "context_hash": sha256_digest({"task_id": task_id, "files": files, "mission": mission}),
            "created_at": utc_now(),
            "source_state_hash": sha256_digest(self._load_memories()),
            "task_id": task_id,
            "provider_role": provider_role,
            "mission": mission,
            "authoritative_state": {
                "active_goals_count": len(active_goals),
                "open_loops_count": len(open_loops),
                "autonomous_spend_limit_eur": 0,
            },
            "relevant_decisions": [asdict(m) for m in active_goals[:3]],
            "security_rules": [
                "AUTONOMOUS_SPEND_LIMIT = 0 EUR",
                "CREDENTIAL_STORAGE = DENY",
                "AUTO_ACCOUNT_LOGIN = DENY",
                "PUBLICATION_AUTHORIZATION_INFERENCE = DENY",
                "PHYSICAL_NODE_B_USED = NO",
            ],
            "money_rules": ["Zero EUR autonomous spend allowed; purchases require PAYMENT_APPROVAL_REQUIRED"],
            "files_in_scope": files,
            "previous_result": None,
            "known_failures": [l["reason"] for l in open_loops if l.get("loop_type") == "RETRY_DECISION_PENDING"],
            "required_tests": ["python3 -m unittest -v tests/test_chief_brain_mission_169.py"],
            "do_not_repeat": ["Do not create duplicate tasks", "Do not create dummy files"],
            "output_contract": {"format": "FINAL_REPORT", "required_fields": ["RESULT", "EVIDENCE"]},
            "stop_conditions": ["Task completed", "Test failed", "Human gate required"],
            "memory_references": [m.memory_id for m in active_rules[:5]],
            "delta_references": [],
            "allowed_actions": ["READ_LOCAL_FILES", "WRITE_SCOPED_FILES", "RUN_LOCAL_TESTS"],
            "forbidden_actions": ["PURCHASE", "PUBLISH", "ACCOUNT_SWITCH", "GIT_COMMIT", "GIT_PUSH"],
        }
        return package

    # --------------------------------------------------------------------------
    # Phase I & W: Bootstrap Context & Handover Snapshot
    # --------------------------------------------------------------------------

    def build_bootstrap_context(self) -> Dict[str, Any]:
        """Generates compact zero-handover bootstrap context for a fresh worker session."""
        active_goals = self.query_memories(item_type="ACTIVE_GOAL")
        user_intents = self.query_memories(item_type="USER_INTENT")
        open_loops = self.get_open_loops()
        running_tasks = self.list_tasks(state="RUNNING")
        recent_results = self.query_memories(item_type="PROVIDER_RESULT")[-3:]

        next_action = self.get_next_action_candidates()
        top_action = next_action[0] if next_action else {"action": "IDLE_NO_READY_WORK"}

        return {
            "BOOTSTRAP_TYPE": "CHIEF_BOOTSTRAP_CONTEXT_V1",
            "CANONICAL_WORKSPACE": str(self.repo_dir),
            "PROJECT_NAME": "2026-courier",
            "TIMESTAMP": utc_now(),
            "ACTIVE_GOALS": [g.summary for g in active_goals[:5]],
            "ACTIVE_USER_INTENTS": [i.summary for i in user_intents[:5]],
            "RUNNING_TASKS": [t.task_id for t in running_tasks],
            "OPEN_LOOPS_COUNT": len(open_loops),
            "OPEN_LOOPS_SAMPLE": open_loops[:5],
            "RECENT_RESULTS_COUNT": len(recent_results),
            "HARD_BOUNDARIES": {
                "AUTONOMOUS_SPEND_LIMIT_EUR": 0.0,
                "PAYMENT_APPROVAL_REQUIRED": True,
                "PUBLICATION_AUTHORIZATION_INFERENCE": "DENY",
                "CREDENTIAL_STORAGE": "DENY",
                "AUTO_ACCOUNT_LOGIN": "DENY",
                "AUTO_ACCOUNT_ROTATION": "DENY",
                "PHYSICAL_NODE_B_USED": "NO",
            },
            "NEXT_RECOMMENDED_ACTION": top_action,
        }

    def generate_handover_snapshot(self) -> Dict[str, Any]:
        """Disaster recovery / audit snapshot generated automatically from brain state."""
        return {
            "SNAPSHOT_TYPE": "CHIEF_HANDOVER_SNAPSHOT_V1",
            "GENERATED_AT": utc_now(),
            "BOOTSTRAP": self.build_bootstrap_context(),
            "ALL_ACTIVE_MEMORIES_COUNT": len(self.query_memories(status="ACTIVE")),
            "IDEAS_INBOX_COUNT": len(self._load_ideas()),
            "TOTAL_TASKS_TRACKED": len(self._load_tasks()),
            "RAW_CHAT_HISTORY_INCLUDED": False,
        }

    # --------------------------------------------------------------------------
    # Phase J: Provider-Independent Task Envelope
    # --------------------------------------------------------------------------

    def build_task_envelope(
        self,
        task_id: str,
        instruction: str,
        provider_role: str = "GOOGLE_BUILD",
        scope_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Builds provider-neutral task envelope consumable by Codex, Antigravity, etc."""
        ctx_pkg = self.build_context_package(task_id=task_id, provider_role=provider_role, scope_files=scope_files)
        envelope = {
            "schema_version": "TASK_ENVELOPE_V1",
            "task_id": task_id,
            "provider_role": provider_role,
            "instruction": instruction,
            "context_package": ctx_pkg,
            "constraints": [
                "AUTONOMOUS_SPEND_LIMIT = 0 EUR",
                "NO_GIT_COMMIT",
                "NO_GIT_PUSH",
                "NO_CREDENTIAL_STORAGE",
            ],
            "success_criteria": [
                "Implementation satisfies instruction",
                "Targeted unit tests pass 100%",
                "0 lint/diff errors",
                "0 secrets detected",
            ],
            "relevant_local_references": scope_files or [],
        }
        return envelope

    # --------------------------------------------------------------------------
    # Phase M: Chief "What Next?" Candidate Generator
    # --------------------------------------------------------------------------

    def get_next_action_candidates(self) -> List[Dict[str, Any]]:
        """Ranks candidate next actions based on goals, open loops, and risk."""
        candidates = []
        open_loops = self.get_open_loops()

        # 1. Unresolved running tasks need monitoring or completion
        for loop in open_loops:
            if loop.get("loop_type") == "UNRESOLVED_TASK":
                candidates.append({
                    "priority": 1,
                    "action_type": "RESOLVE_IN_FLIGHT_TASK",
                    "task_id": loop.get("task_id"),
                    "reason": f"Active task {loop.get('task_id')} is currently {loop.get('state')}",
                    "risk": "LOW",
                })
            elif loop.get("loop_type") == "RETRY_DECISION_PENDING":
                candidates.append({
                    "priority": 2,
                    "action_type": "RETRY_OR_CLOSE_FAILED_TASK",
                    "task_id": loop.get("task_id"),
                    "reason": "Failed task requires retry or closing",
                    "risk": "LOW",
                })
            elif loop.get("loop_type") == "UNPLANNED_IDEA":
                candidates.append({
                    "priority": 3,
                    "action_type": "PLAN_NEW_IDEA",
                    "idea_id": loop.get("idea_id"),
                    "reason": f"Idea {loop.get('idea_id')} ready for clarification and planning",
                    "risk": "LOW",
                })

        # 2. Ready active goals
        active_goals = self.query_memories(item_type="ACTIVE_GOAL")
        for g in active_goals:
            candidates.append({
                "priority": 4,
                "action_type": "EXECUTE_GOAL_STEP",
                "goal_id": g.memory_id,
                "reason": f"Continue progress on active goal: {g.summary}",
                "risk": "LOW",
            })

        if not candidates:
            candidates.append({
                "priority": 99,
                "action_type": "IDLE_AWAIT_USER_INTENT",
                "reason": "No pending tasks or unfulfilled active goals in Chief Brain",
                "risk": "NONE",
            })

        return sorted(candidates, key=lambda c: c["priority"])

    # --------------------------------------------------------------------------
    # Phase P: Brain Compaction (Hot / Warm / Archive)
    # --------------------------------------------------------------------------

    def compact_brain(self) -> Dict[str, Any]:
        """Compacts memories into Hot / Warm / Archive tiers without destroying provenance."""
        memories = self._load_memories()
        hot = {}
        warm = {}
        archived = {}

        now = dt.datetime.now(dt.timezone.utc)

        for mid, mdata in memories.items():
            status = mdata.get("status")
            item_type = mdata.get("item_type")

            if status in ("SUPERSEDED", "REJECTED", "TOMBSTONE"):
                archived[mid] = mdata
            elif status == "COMPLETED":
                # Check age
                try:
                    updated = dt.datetime.fromisoformat(mdata.get("updated_at", utc_now()))
                    if (now - updated).days > 7:
                        archived[mid] = mdata
                    else:
                        warm[mid] = mdata
                except Exception:
                    warm[mid] = mdata
            elif item_type in ("USER_INTENT", "ACTIVE_GOAL", "PROJECT_RULE", "SECURITY_BOUNDARY"):
                hot[mid] = mdata
            else:
                warm[mid] = mdata

        # Write hot + warm as active memories
        active_combined = {**hot, **warm}
        self._save_memories(active_combined)

        # Write archive
        archive_file = self.archive_dir / f"archive-{now.strftime('%Y%m%d')}.json"
        existing_archive = read_json_safe(archive_file, {})
        if not isinstance(existing_archive, dict):
            existing_archive = {}
        existing_archive.update(archived)
        atomic_write_json(archive_file, existing_archive)

        return {
            "hot_count": len(hot),
            "warm_count": len(warm),
            "archived_count": len(archived),
            "archive_file": str(archive_file),
        }

    # --------------------------------------------------------------------------
    # Phase Y: Migration of Existing Curated Records
    # --------------------------------------------------------------------------

    def migrate_existing_state(self) -> Dict[str, int]:
        """Migrates curated existing decisions, goals, and opportunities into canonical brain."""
        migrated_count = 0

        # 1. Migrate chief-decisions if present
        decisions_dir = self.repo_dir / "events" / "chief-decisions"
        if decisions_dir.is_dir():
            for p in decisions_dir.glob("*.json"):
                data = read_json_safe(p)
                if isinstance(data, dict):
                    dec_id = data.get("chief_decision_id") or data.get("decision_id") or p.stem
                    if not self.get_memory(f"migrated-{dec_id}"):
                        mem = MemoryItem(
                            memory_id=f"migrated-{dec_id}",
                            item_type="HISTORICAL_DECISION",
                            content=json.dumps(data),
                            summary=f"Migrated decision {dec_id}: {data.get('decision', 'UNKNOWN')}",
                            source="MIGRATED_CURATED_RECORD",
                            confidence="HIGH",
                        )
                        self.record_memory(mem)
                        migrated_count += 1

        # 2. Establish foundational rules and policies
        rules = [
            ("rule-workspace-truth", "WORKSPACE_SOURCE_OF_TRUTH: Local workspace /Users/user/Downloads/2026-courier is canonical; provider chats are replaceable workers."),
            ("rule-cost-firewall", "AUTONOMOUS_SPEND_LIMIT = 0 EUR. Payment approval required for paid tiers (CostGate)."),
            ("rule-pub-firewall", "PUBLICATION_AUTHORIZATION_INFERENCE = DENY. Releases require explicit human gate."),
            ("rule-sec-secrets", "CREDENTIAL_STORAGE = DENY. Passwords, tokens, and OAuth keys forbidden fail-closed."),
            ("rule-two-pc-isolation", "PHYSICAL_NODE_B_USED = NO. Computer B remains offline and isolated."),
            ("rule-heavy-limit", "HEAVY_JOB_LIMIT = 1. At most one heavy job executed at a time per node."),
            ("rule-vs-server", "PERSISTENT_EXPECTED_SERVICE: scripts/run_visual_studio_server.py is expected infrastructure, not hung."),
            ("rule-multi-pool", "MULTI_POOL_INDEPENDENCE: Multiple resource pools remain independent; quotas from different accounts are never summed."),
            ("rule-waste-policy", "WASTE_CAPACITY_POLICY: HUNG, DUPLICATE, or NO_INFORMATION_GAIN work does not justify capacity expansion."),
            ("rule-high-risk-review", "HIGH_RISK_REVIEW_POLICY: High-risk security/publication changes require independent review before activation."),
            ("rule-creator-factory", "CREATOR_FACTORY_STRATEGY: 3D Godot creator video pipeline is an active strategic production direction."),
        ]
        for rid, rtext in rules:
            if not self.get_memory(rid):
                mem = MemoryItem(
                    memory_id=rid,
                    item_type="PROJECT_RULE",
                    content=rtext,
                    summary=rtext,
                    source="FOUNDATIONAL_POLICY",
                    confidence="HIGH",
                )
                self.record_memory(mem)
                migrated_count += 1

        # 3. Migrate standing objectives
        obj_dir = self.repo_dir / "events" / "standing-objectives"
        if obj_dir.is_dir():
            for p in obj_dir.glob("*.json"):
                data = read_json_safe(p)
                if isinstance(data, dict):
                    obj_id = data.get("objective_id", p.stem)
                    mid = f"obj-{obj_id}"
                    if not self.get_memory(mid):
                        status = "COMPLETED" if data.get("status") == "COMPLETE" else "ACTIVE"
                        mem = MemoryItem(
                            memory_id=mid,
                            item_type="ACTIVE_GOAL" if status == "ACTIVE" else "HISTORICAL_DECISION",
                            content=json.dumps(data),
                            summary=f"Standing Objective: {data.get('name', obj_id)}",
                            status=status,
                            source="MIGRATED_OBJECTIVE",
                            confidence="HIGH",
                        )
                        self.record_memory(mem)
                        migrated_count += 1

        # 4. Migrate active creator factory goal
        active_creator_goal_id = "goal-creator-factory-autonomy"
        if not self.get_memory(active_creator_goal_id):
            mem = MemoryItem(
                memory_id=active_creator_goal_id,
                item_type="ACTIVE_GOAL",
                content="Execute autonomous production loop for 3D Godot creator video factory within 0 EUR spend limit.",
                summary="3D Godot Creator Factory Autonomous Production Loop",
                status="ACTIVE",
                source="HUMAN_EXPLICIT",
                confidence="HIGH",
            )
            self.record_memory(mem)
            migrated_count += 1

        return {"migrated_records": migrated_count}


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical Persistent Chief Brain (Mission 169)")
    parser.add_argument("--status", action="store_true", help="Print Chief Brain status")
    parser.add_argument("--bootstrap", action="store_true", help="Generate compact bootstrap context")
    parser.add_argument("--handover", action="store_true", help="Generate DR handover snapshot")
    parser.add_argument("--remember", type=str, help="Record durable user intent")
    parser.add_argument("--idea", type=str, help="Record idea in inbox")
    parser.add_argument("--compact", action="store_true", help="Compact brain memories")
    parser.add_argument("--migrate", action="store_true", help="Migrate existing curated state")
    args = parser.parse_args()

    brain = ChiefBrain()

    if args.migrate:
        res = brain.migrate_existing_state()
        print(f"✅ Migrated {res['migrated_records']} curated records into Chief Brain.")

    if args.remember:
        item = brain.record_user_intent(args.remember)
        print(f"✅ Recorded durable intent: {item.memory_id} -> {item.summary}")

    if args.idea:
        idea = brain.record_idea(args.idea)
        print(f"✅ Recorded idea in inbox: {idea.idea_id} -> {idea.normalized_interpretation}")

    if args.compact:
        res = brain.compact_brain()
        print(f"✅ Brain compacted: {res['hot_count']} hot, {res['warm_count']} warm, {res['archived_count']} archived.")

    if args.bootstrap or len(sys.argv) == 1:
        boot = brain.build_bootstrap_context()
        print(json.dumps(boot, indent=2))

    if args.handover:
        ho = brain.generate_handover_snapshot()
        print(json.dumps(ho, indent=2))


if __name__ == "__main__":
    main()

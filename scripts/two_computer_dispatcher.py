#!/usr/bin/env python3
"""Two-Computer Autonomous Worker Dispatcher & Control-Plane (Mission 161G & 165G/166G Hardened).

Provides deterministic orchestration for two computers (Node A and Node B):
- OS-level atomic lease creation (fcntl.flock exclusive transactions)
- Crash-recoverable claim transactions with write-ahead transaction records (no split-brain)
- Fail-closed lease expiry reconciliation with strict node/task/lease/digest matching
- Durable, provenance-bound safe-to-requeue evidence verification
- Immutable result identity with SHA-256 canonical digest validation & strict idempotency
- Protected File-Scope Locking with directory-prefix conflict detection
- Per-node Heavy Job Limits (HEAVY_JOB_LIMIT = 1)
- Separate Google Resource Pool Routing (no percentage summing, no credential storage)
- Restart Recovery with safe reconciliation
- Transport Adapter Interface for local and shared-state environments.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import sys
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Protocol, Set, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
CLUSTER_DIR = RUNTIME_DIR / "cluster"
RESULTS_DIR = CLUSTER_DIR / "results"

HEARTBEAT_STALE_SECONDS_DEFAULT = 60.0
LEASE_DURATION_SECONDS_DEFAULT = 300.0  # 5 minutes
HEAVY_JOB_LIMIT_PER_NODE = 1

ALLOWED_POOLS = {
    "GOOGLE_PRO_POOL_1",
    "GOOGLE_PRO_POOL_2",
    "GOOGLE_PRO_POOL_3",
    "GOOGLE_PRO_POOL_4_NOT_CONFIGURED",
}

VALID_SAFE_REQUEUE_CLASSES = {
    "EXECUTION_NEVER_STARTED_PROVEN",
    "AUTHORITATIVE_WORKER_ABORT_BEFORE_MUTATION",
    "DETERMINISTIC_CLEAN_ABORT",
}


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_iso(ts_str: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts_str)


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class NodeRecord:
    node_id: str  # e.g. "NODE_A", "NODE_B"
    hostname: str
    platform: str
    workspace_path: str
    worktree_path: str
    status: str = "UNKNOWN"  # UNKNOWN, IDLE, READY, ACTIVE, BLOCKED, RESOURCE_BLOCKED, HUMAN_GATE, HUNG, OFFLINE
    last_heartbeat: str = field(default_factory=utc_now_iso)
    capabilities: List[str] = field(default_factory=list)
    resource_pool: str = "GOOGLE_PRO_POOL_1"
    current_task_id: Optional[str] = None
    current_lease_id: Optional[str] = None
    current_file_scope: List[str] = field(default_factory=list)
    heavy_job_active: bool = False
    continuation_state: Optional[str] = None
    last_result_id: Optional[str] = None


@dataclass
class TaskRecord:
    task_id: str
    title: str
    task_type: str  # TEST, RENDER, AUDIT, REMEDIATION, ASSET_BUILD, VERIFICATION
    priority: int = 5  # 1 (highest) to 10 (lowest)
    risk: str = "LOW"  # LOW, MEDIUM, HIGH
    required_capabilities: List[str] = field(default_factory=list)
    preferred_node: Optional[str] = None
    required_resource_pool: Optional[str] = None
    file_scope: List[str] = field(default_factory=list)
    exclusive_scope: bool = True
    heavy_job: bool = False
    status: str = "READY"  # READY, LEASED, RUNNING, BLOCKED, RECONCILIATION_REQUIRED, HUMAN_GATE, COMPLETE, FAILED_SAFE, CANCELLED
    created_at: str = field(default_factory=utc_now_iso)
    lease_owner: Optional[str] = None
    lease_id: Optional[str] = None
    lease_expires_at: Optional[str] = None
    attempt_count: int = 0
    result_id: Optional[str] = None
    result_digest: Optional[str] = None
    accepted_node_id: Optional[str] = None
    accepted_lease_id: Optional[str] = None
    stop_reason: Optional[str] = None


@dataclass
class LeaseRecord:
    lease_id: str
    node_id: str
    task_id: str
    file_scope: List[str]
    heavy_job: bool
    acquired_at: str
    expires_at: str
    status: str = "ACTIVE"  # ACTIVE, RELEASED, EXPIRED, EXPIRED_UNCERTAIN, CANCELLED


@dataclass
class ClaimTransactionRecord:
    tx_id: str
    node_id: str
    task_id: str
    lease_id: str
    status: str  # PREPARED, COMMITTED, ABORTED
    created_at: str = field(default_factory=utc_now_iso)
    committed_at: Optional[str] = None


@dataclass
class WorkerResultRecord:
    result_id: str
    task_id: str
    node_id: str
    lease_id: str
    status: str  # SUCCESS, FAILURE, HUMAN_GATE_REQUIRED, BLOCKED_SAFE
    started_at: str
    finished_at: str
    files_changed: List[str] = field(default_factory=list)
    checks_run: List[str] = field(default_factory=list)
    summary: str = ""
    next_state: str = "IDLE"
    result_digest: Optional[str] = None


@dataclass
class SafeRequeueEvidenceRecord:
    evidence_id: str
    task_id: str
    lease_id: str
    node_id: str
    evidence_class: str  # EXECUTION_NEVER_STARTED_PROVEN, AUTHORITATIVE_WORKER_ABORT_BEFORE_MUTATION, DETERMINISTIC_CLEAN_ABORT
    created_at: str = field(default_factory=utc_now_iso)
    source: str = "LOCAL_AUTHORITATIVE_CONTROLLER"
    evidence_digest: str = ""


# ==============================================================================
# Canonical Digest Computations
# ==============================================================================

def compute_result_digest(result: WorkerResultRecord) -> str:
    """Computes a deterministic SHA-256 digest of all immutable result fields."""
    canonical_obj = {
        "checks_run": sorted(result.checks_run),
        "files_changed": sorted(result.files_changed),
        "finished_at": result.finished_at,
        "lease_id": result.lease_id,
        "next_state": result.next_state,
        "node_id": result.node_id,
        "result_id": result.result_id,
        "started_at": result.started_at,
        "status": result.status,
        "summary": result.summary,
        "task_id": result.task_id,
    }
    canonical_json = json.dumps(canonical_obj, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_evidence_digest(ev: Union[SafeRequeueEvidenceRecord, Dict[str, Any]]) -> str:
    """Computes a deterministic SHA-256 digest of an evidence record."""
    if isinstance(ev, SafeRequeueEvidenceRecord):
        canonical_obj = {
            "evidence_class": ev.evidence_class,
            "evidence_id": ev.evidence_id,
            "lease_id": ev.lease_id,
            "node_id": ev.node_id,
            "source": ev.source,
            "task_id": ev.task_id,
        }
    else:
        canonical_obj = {
            "evidence_class": ev.get("evidence_class", ""),
            "evidence_id": ev.get("evidence_id", ""),
            "lease_id": ev.get("lease_id", ""),
            "node_id": ev.get("node_id", ""),
            "source": ev.get("source", ""),
            "task_id": ev.get("task_id", ""),
        }
    canonical_json = json.dumps(canonical_obj, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# ==============================================================================
# Scope Overlap & Collision Resolver
# ==============================================================================

class ScopeLockManager:
    """Manages file-scope collision detection with directory-prefix awareness."""

    @staticmethod
    def normalize_path(path_str: str) -> str:
        p = path_str.strip().replace("\\", "/")
        if not p.startswith("/"):
            p = "/" + p
        return p

    @classmethod
    def paths_overlap(cls, path_a: str, path_b: str) -> bool:
        norm_a = cls.normalize_path(path_a)
        norm_b = cls.normalize_path(path_b)

        if norm_a == norm_b:
            return True

        # Check directory-prefix containment
        if norm_a.endswith("/"):
            if norm_b.startswith(norm_a):
                return True
        else:
            if norm_b.startswith(norm_a + "/"):
                return True

        if norm_b.endswith("/"):
            if norm_a.startswith(norm_b):
                return True
        else:
            if norm_a.startswith(norm_b + "/"):
                return True

        return False

    @classmethod
    def check_scope_collision(
        cls, candidate_scope: List[str], active_leases: List[LeaseRecord]
    ) -> Optional[Tuple[str, str, str]]:
        """Returns (colliding_path_candidate, colliding_path_active, active_lease_id) if conflict exists."""
        for c_path in candidate_scope:
            for lease in active_leases:
                if lease.status in ("ACTIVE", "EXPIRED_UNCERTAIN"):
                    for a_path in lease.file_scope:
                        if cls.paths_overlap(c_path, a_path):
                            return (c_path, a_path, lease.lease_id)
        return None


# ==============================================================================
# Transport Adapter Interface
# ==============================================================================

class TransportAdapter(Protocol):
    def read_json(self, rel_path: str) -> Optional[Dict[str, Any]]: ...
    def write_json(self, rel_path: str, data: Dict[str, Any]) -> None: ...
    def list_files(self, rel_dir: str) -> List[str]: ...
    def transaction(self) -> Iterator[None]: ...


class LocalDurableTransportAdapter:
    """Filesystem-backed transport adapter operating inside the cluster state directory."""

    def __init__(self, root_dir: Path = CLUSTER_DIR):
        self.root_dir = root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file_path = self.root_dir / ".cluster.lock"
        self._lock_depth = 0
        self._lock_file: Optional[Any] = None

    def _resolve(self, rel_path: str) -> Path:
        return self.root_dir / rel_path

    def read_json(self, rel_path: str) -> Optional[Dict[str, Any]]:
        p = self._resolve(rel_path)
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def write_json(self, rel_path: str, data: Dict[str, Any]) -> None:
        p = self._resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        temp_file = p.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(p)

    def list_files(self, rel_dir: str) -> List[str]:
        d = self._resolve(rel_dir)
        if not d.is_dir():
            return []
        return [f.name for f in d.iterdir() if f.is_file()]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Provides an exclusive, reentrant OS-backed process lock for atomic state transitions."""
        if self._lock_depth == 0:
            self._lock_file = open(self.lock_file_path, "a+")
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX)
        self._lock_depth += 1
        try:
            yield
        finally:
            self._lock_depth -= 1
            if self._lock_depth == 0:
                if self._lock_file:
                    try:
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                        self._lock_file.close()
                    except Exception:
                        pass
                    self._lock_file = None


# ==============================================================================
# Two-Computer Dispatcher Engine
# ==============================================================================

class TwoComputerDispatcher:
    """Unified Control-Plane coordinating Node A and Node B."""

    def __init__(
        self,
        transport: Optional[TransportAdapter] = None,
        heartbeat_stale_seconds: float = HEARTBEAT_STALE_SECONDS_DEFAULT,
        lease_duration_seconds: float = LEASE_DURATION_SECONDS_DEFAULT,
    ):
        self.transport = transport or LocalDurableTransportAdapter()
        self.heartbeat_stale_seconds = heartbeat_stale_seconds
        self.lease_duration_seconds = lease_duration_seconds
        self._init_storage()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        if hasattr(self.transport, "transaction"):
            with self.transport.transaction():
                yield
        else:
            yield

    def _init_storage(self) -> None:
        with self._transaction():
            if not self.transport.read_json("node_registry.json"):
                self.transport.write_json("node_registry.json", {"nodes": {}})
            if not self.transport.read_json("task_queue.json"):
                self.transport.write_json("task_queue.json", {"tasks": {}})
            if not self.transport.read_json("active_leases.json"):
                self.transport.write_json("active_leases.json", {"leases": {}})
            if not self.transport.read_json("claim_transactions.json"):
                self.transport.write_json("claim_transactions.json", {"transactions": {}})
            self._reconcile_transactions()

    def _reconcile_transactions(self) -> None:
        """Rolls back incomplete / uncommitted claim transactions to eliminate split-brain."""
        lease_data = self.transport.read_json("active_leases.json") or {"leases": {}}
        leases = lease_data.get("leases", {})
        queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
        tasks = queue_data.get("tasks", {})
        tx_data = self.transport.read_json("claim_transactions.json") or {"transactions": {}}
        txs = tx_data.get("transactions", {})
        reg_data = self.transport.read_json("node_registry.json") or {"nodes": {}}
        nodes = reg_data.get("nodes", {})

        mutated = False
        for lid, l_dict in list(leases.items()):
            if l_dict.get("status") == "ACTIVE":
                tid = l_dict.get("task_id")
                t_dict = tasks.get(tid)

                # Check if corresponding task is NOT leased with this lease_id
                is_split_brain = (
                    t_dict is None
                    or t_dict.get("status") == "READY"
                    or t_dict.get("lease_id") != lid
                )

                if is_split_brain:
                    # Incomplete claim crash artifact: roll back lease
                    l_dict["status"] = "CANCELLED"
                    mutated = True
                    nid = l_dict.get("node_id")
                    if nid in nodes and nodes[nid].get("current_lease_id") == lid:
                        nodes[nid]["current_task_id"] = None
                        nodes[nid]["current_lease_id"] = None
                        nodes[nid]["current_file_scope"] = []
                        nodes[nid]["heavy_job_active"] = False
                        if nodes[nid].get("status") == "ACTIVE":
                            nodes[nid]["status"] = "READY"

        if mutated:
            self.transport.write_json("active_leases.json", {"leases": leases})
            self.transport.write_json("node_registry.json", {"nodes": nodes})

    # --------------------------------------------------------------------------
    # Node Registry & Heartbeats
    # --------------------------------------------------------------------------

    def register_node(
        self,
        node_id: str,
        hostname: str,
        platform: str,
        workspace_path: str,
        worktree_path: str,
        capabilities: Optional[List[str]] = None,
        resource_pool: str = "GOOGLE_PRO_POOL_1",
    ) -> NodeRecord:
        with self._transaction():
            registry = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = registry.get("nodes", {})

            record = NodeRecord(
                node_id=node_id,
                hostname=hostname,
                platform=platform,
                workspace_path=workspace_path,
                worktree_path=worktree_path,
                status="READY",
                last_heartbeat=utc_now_iso(),
                capabilities=capabilities or ["local_compute", "python_test", "creator_pipeline"],
                resource_pool=resource_pool,
            )
            nodes[node_id] = asdict(record)
            self.transport.write_json("node_registry.json", {"nodes": nodes})
            return record

    def heartbeat(
        self,
        node_id: str,
        status: Optional[str] = None,
        continuation_state: Optional[str] = None,
    ) -> Optional[NodeRecord]:
        with self._transaction():
            registry = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = registry.get("nodes", {})
            if node_id not in nodes:
                return None

            node_data = nodes[node_id]
            node_data["last_heartbeat"] = utc_now_iso()
            if status:
                node_data["status"] = status
            if continuation_state:
                node_data["continuation_state"] = continuation_state

            nodes[node_id] = node_data
            self.transport.write_json("node_registry.json", {"nodes": nodes})
            return NodeRecord(**node_data)

    def reconcile_stale_nodes(self) -> List[str]:
        """Detects nodes with stale heartbeats and marks them OFFLINE."""
        with self._transaction():
            registry = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = registry.get("nodes", {})
            now = datetime.datetime.now(datetime.timezone.utc)
            stale_node_ids = []

            for nid, data in nodes.items():
                last_hb = parse_iso(data["last_heartbeat"])
                elapsed = (now - last_hb).total_seconds()
                if elapsed > self.heartbeat_stale_seconds and data["status"] not in ("OFFLINE", "HUMAN_GATE"):
                    data["status"] = "OFFLINE"
                    stale_node_ids.append(nid)

            if stale_node_ids:
                self.transport.write_json("node_registry.json", {"nodes": nodes})
            return stale_node_ids

    def get_node(self, node_id: str) -> Optional[NodeRecord]:
        registry = self.transport.read_json("node_registry.json") or {"nodes": {}}
        nodes = registry.get("nodes", {})
        if node_id in nodes:
            return NodeRecord(**nodes[node_id])
        return None

    def list_nodes(self) -> List[NodeRecord]:
        registry = self.transport.read_json("node_registry.json") or {"nodes": {}}
        return [NodeRecord(**d) for d in registry.get("nodes", {}).values()]

    # --------------------------------------------------------------------------
    # Task Queue
    # --------------------------------------------------------------------------

    def submit_task(
        self,
        title: str,
        task_type: str,
        file_scope: List[str],
        priority: int = 5,
        risk: str = "LOW",
        required_capabilities: Optional[List[str]] = None,
        preferred_node: Optional[str] = None,
        required_resource_pool: Optional[str] = None,
        heavy_job: bool = False,
        task_id: Optional[str] = None,
    ) -> TaskRecord:
        with self._transaction():
            queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
            tasks = queue_data.get("tasks", {})

            tid = task_id or f"TASK-{uuid.uuid4().hex[:8].upper()}"
            task = TaskRecord(
                task_id=tid,
                title=title,
                task_type=task_type,
                priority=priority,
                risk=risk,
                required_capabilities=required_capabilities or [],
                preferred_node=preferred_node,
                required_resource_pool=required_resource_pool,
                file_scope=file_scope,
                heavy_job=heavy_job,
                status="READY",
                created_at=utc_now_iso(),
            )
            tasks[tid] = asdict(task)
            self.transport.write_json("task_queue.json", {"tasks": tasks})
            return task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
        tasks = queue_data.get("tasks", {})
        if task_id in tasks:
            return TaskRecord(**tasks[task_id])
        return None

    def list_tasks(self, status: Optional[str] = None) -> List[TaskRecord]:
        queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
        tasks = [TaskRecord(**d) for d in queue_data.get("tasks", {}).values()]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: (t.priority, t.created_at))

    # --------------------------------------------------------------------------
    # Atomic Leases & Scope Locking
    # --------------------------------------------------------------------------

    def get_active_leases(self) -> List[LeaseRecord]:
        with self._transaction():
            self._reconcile_transactions()
            lease_data = self.transport.read_json("active_leases.json") or {"leases": {}}
            queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
            tasks = queue_data.get("tasks", {})

            active = []
            for d in lease_data.get("leases", {}).values():
                if d.get("status") in ("ACTIVE", "EXPIRED_UNCERTAIN"):
                    tid = d.get("task_id")
                    t_rec = tasks.get(tid)
                    if t_rec and t_rec.get("lease_id") == d.get("lease_id"):
                        active.append(LeaseRecord(**d))
            return active

    def reconcile_expired_leases(
        self, safe_requeue_evidence: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Detects expired leases and performs fail-closed reconciliation.

        CRITICAL: Lease expiry alone NEVER automatically resets a task to READY.
        - If completion is proven by a matching durable result (with node_id, task_id, lease_id matching) -> COMPLETE.
        - If verified durable safe non-execution evidence record is provided -> SAFE_TO_REQUEUE -> READY.
        - Raw boolean safe_to_requeue is strictly REJECTED.
        - If state is uncertain -> mark EXPIRED_UNCERTAIN and RECONCILIATION_REQUIRED (never redispatch).
        """
        with self._transaction():
            self._reconcile_transactions()
            lease_data = self.transport.read_json("active_leases.json") or {"leases": {}}
            leases = lease_data.get("leases", {})
            queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
            tasks = queue_data.get("tasks", {})
            reg_data = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = reg_data.get("nodes", {})

            now = datetime.datetime.now(datetime.timezone.utc)
            reconciled_ids = []

            for lid, l_data in list(leases.items()):
                if l_data.get("status") == "ACTIVE":
                    exp = parse_iso(l_data["expires_at"])
                    if now > exp:
                        tid = l_data["task_id"]
                        nid = l_data["node_id"]

                        # Check 1: Is matching durable result present with strict task + lease + node matching?
                        matching_result = None
                        results_dir = (self.transport.root_dir / "results") if hasattr(self.transport, "root_dir") else RESULTS_DIR
                        if results_dir.is_dir():
                            for res_file in results_dir.glob("*.json"):
                                try:
                                    r_data = json.loads(res_file.read_text(encoding="utf-8"))
                                    # Strict validation: task_id, lease_id, AND node_id MUST match!
                                    if (
                                        r_data.get("task_id") == tid
                                        and r_data.get("lease_id") == lid
                                        and r_data.get("node_id") == nid
                                    ):
                                        matching_result = r_data
                                        break
                                except Exception:
                                    pass

                        if matching_result and matching_result.get("status") == "SUCCESS":
                            # Completion proven by authoritative matching durable result
                            l_data["status"] = "RELEASED"
                            if tid in tasks:
                                tasks[tid]["status"] = "COMPLETE"
                                tasks[tid]["result_id"] = matching_result.get("result_id")
                                tasks[tid]["result_digest"] = matching_result.get("result_digest") or compute_result_digest(
                                    WorkerResultRecord(
                                        result_id=matching_result.get("result_id", ""),
                                        task_id=tid,
                                        node_id=nid,
                                        lease_id=lid,
                                        status="SUCCESS",
                                        started_at=matching_result.get("started_at", ""),
                                        finished_at=matching_result.get("finished_at", ""),
                                        files_changed=matching_result.get("files_changed", []),
                                        checks_run=matching_result.get("checks_run", []),
                                        summary=matching_result.get("summary", ""),
                                        next_state=matching_result.get("next_state", "IDLE"),
                                    )
                                )
                                tasks[tid]["accepted_node_id"] = nid
                                tasks[tid]["accepted_lease_id"] = lid
                                tasks[tid]["lease_owner"] = None
                                tasks[tid]["lease_id"] = None
                                tasks[tid]["lease_expires_at"] = None
                            if nid in nodes:
                                nodes[nid]["current_task_id"] = None
                                nodes[nid]["current_lease_id"] = None
                                nodes[nid]["current_file_scope"] = []
                                nodes[nid]["heavy_job_active"] = False
                                if nodes[nid].get("status") == "ACTIVE":
                                    nodes[nid]["status"] = "READY"
                            reconciled_ids.append(lid)

                        else:
                            # Check 2: Authoritative durable safe-to-requeue evidence
                            evidence_valid = False
                            if safe_requeue_evidence and lid in safe_requeue_evidence:
                                ev_entry = safe_requeue_evidence[lid]
                                # Reject raw unproven booleans
                                if isinstance(ev_entry, dict) and "evidence_class" in ev_entry:
                                    ev_class = ev_entry.get("evidence_class")
                                    ev_task = ev_entry.get("task_id")
                                    ev_lease = ev_entry.get("lease_id")
                                    ev_node = ev_entry.get("node_id")

                                    if (
                                        ev_class in VALID_SAFE_REQUEUE_CLASSES
                                        and ev_task == tid
                                        and ev_lease == lid
                                        and ev_node == nid
                                    ):
                                        evidence_valid = True

                            if evidence_valid:
                                # Explicit verified evidence of clean termination
                                l_data["status"] = "EXPIRED"
                                if tid in tasks:
                                    tasks[tid]["status"] = "READY"
                                    tasks[tid]["lease_owner"] = None
                                    tasks[tid]["lease_id"] = None
                                    tasks[tid]["lease_expires_at"] = None
                                if nid in nodes:
                                    nodes[nid]["current_task_id"] = None
                                    nodes[nid]["current_lease_id"] = None
                                    nodes[nid]["current_file_scope"] = []
                                    nodes[nid]["heavy_job_active"] = False
                                    if nodes[nid].get("status") == "ACTIVE":
                                        nodes[nid]["status"] = "READY"
                                reconciled_ids.append(lid)
                            else:
                                # UNCERTAIN: Fail-closed. Mark RECONCILIATION_REQUIRED. Do NOT redispatch.
                                l_data["status"] = "EXPIRED_UNCERTAIN"
                                if tid in tasks:
                                    tasks[tid]["status"] = "RECONCILIATION_REQUIRED"
                                    tasks[tid]["stop_reason"] = "LEASE_EXPIRED_UNCERTAIN_ORIGINAL_EXECUTION"
                                if nid in nodes and nodes[nid].get("current_lease_id") == lid:
                                    nodes[nid]["status"] = "BLOCKED"
                                reconciled_ids.append(lid)

            if reconciled_ids:
                self.transport.write_json("active_leases.json", {"leases": leases})
                self.transport.write_json("task_queue.json", {"tasks": tasks})
                self.transport.write_json("node_registry.json", {"nodes": nodes})
            return reconciled_ids

    def claim_task_lease(self, node_id: str, task_id: str) -> Tuple[bool, str, Optional[LeaseRecord]]:
        """Atomically leases a task to a node with transactional crash-recovery protections."""
        with self._transaction():
            self._reconcile_transactions()
            self.reconcile_stale_nodes()
            self.reconcile_expired_leases()

            # 1. Validate Task
            task = self.get_task(task_id)
            if not task:
                return False, f"Task {task_id} not found", None
            if task.status != "READY":
                return False, f"Task {task_id} is in status {task.status}, not READY (ALREADY_CLAIMED)", None

            # 2. Validate Node
            node = self.get_node(node_id)
            if not node:
                return False, f"Node {node_id} not registered", None
            if node.status not in ("READY", "IDLE"):
                if node.heavy_job_active or task.heavy_job:
                    return False, f"Node {node_id} already has a heavy job active (HEAVY_JOB_LIMIT=1, status: {node.status})", None
                return False, f"Node {node_id} status is {node.status}, cannot take new lease", None

            # 3. Capability Check
            if not set(task.required_capabilities).issubset(set(node.capabilities)):
                return False, f"Node {node_id} missing required capabilities: {set(task.required_capabilities) - set(node.capabilities)}", None

            # 4. Resource Pool Check
            if task.required_resource_pool and task.required_resource_pool != node.resource_pool:
                return False, f"Node {node_id} pool {node.resource_pool} != required {task.required_resource_pool}", None

            # 5. Heavy Job Limit Check (HEAVY_JOB_LIMIT = 1)
            if task.heavy_job and node.heavy_job_active:
                return False, f"Node {node_id} already has a heavy job active (HEAVY_JOB_LIMIT=1)", None

            # 6. File Scope Overlap Check
            active_leases = self.get_active_leases()
            collision = ScopeLockManager.check_scope_collision(task.file_scope, active_leases)
            if collision:
                c_cand, c_act, c_lid = collision
                return False, f"File scope collision: '{c_cand}' overlaps with active lease '{c_lid}' ('{c_act}')", None

            # 7. Write-Ahead Transaction Preparation
            tx_id = f"tx-{uuid.uuid4().hex[:12]}"
            lease_id = f"lease-{uuid.uuid4().hex[:12]}"
            now = datetime.datetime.now(datetime.timezone.utc)
            expires_at = (now + datetime.timedelta(seconds=self.lease_duration_seconds)).isoformat()

            tx_record = ClaimTransactionRecord(
                tx_id=tx_id,
                node_id=node_id,
                task_id=task_id,
                lease_id=lease_id,
                status="PREPARED",
                created_at=now.isoformat(),
            )
            tx_data = self.transport.read_json("claim_transactions.json") or {"transactions": {}}
            tx_data.setdefault("transactions", {})[tx_id] = asdict(tx_record)
            self.transport.write_json("claim_transactions.json", tx_data)

            # 8. Atomic Claim Persistence
            lease = LeaseRecord(
                lease_id=lease_id,
                node_id=node_id,
                task_id=task_id,
                file_scope=task.file_scope,
                heavy_job=task.heavy_job,
                acquired_at=now.isoformat(),
                expires_at=expires_at,
                status="ACTIVE",
            )

            # Update Leases
            lease_data = self.transport.read_json("active_leases.json") or {"leases": {}}
            lease_data.setdefault("leases", {})[lease_id] = asdict(lease)
            self.transport.write_json("active_leases.json", lease_data)

            # Update Task
            queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
            tasks = queue_data.get("tasks", {})
            t_dict = tasks[task_id]
            t_dict["status"] = "LEASED"
            t_dict["lease_owner"] = node_id
            t_dict["lease_id"] = lease_id
            t_dict["lease_expires_at"] = expires_at
            t_dict["attempt_count"] = t_dict.get("attempt_count", 0) + 1
            self.transport.write_json("task_queue.json", queue_data)

            # Update Node
            reg_data = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = reg_data.get("nodes", {})
            n_dict = nodes[node_id]
            n_dict["status"] = "ACTIVE"
            n_dict["current_task_id"] = task_id
            n_dict["current_lease_id"] = lease_id
            n_dict["current_file_scope"] = task.file_scope
            n_dict["heavy_job_active"] = task.heavy_job
            self.transport.write_json("node_registry.json", reg_data)

            # 9. Mark Transaction Committed
            tx_record.status = "COMMITTED"
            tx_record.committed_at = utc_now_iso()
            tx_data["transactions"][tx_id] = asdict(tx_record)
            self.transport.write_json("claim_transactions.json", tx_data)

            return True, f"Lease {lease_id} acquired successfully", lease

    def dispatch_next_task(self, node_id: str) -> Optional[Tuple[TaskRecord, LeaseRecord]]:
        """Selects and leases the highest-priority eligible task for the given node."""
        try:
            from scripts.single_flight import is_single_flight_locked
        except ImportError:
            from single_flight import is_single_flight_locked
        if is_single_flight_locked(self.root_dir.parent.parent):
            return None

        with self._transaction():
            ready_tasks = self.list_tasks(status="READY")
            for task in ready_tasks:
                if task.preferred_node and task.preferred_node != node_id:
                    continue
                success, msg, lease = self.claim_task_lease(node_id, task.task_id)
                if success and lease:
                    return task, lease
            return None

    # --------------------------------------------------------------------------
    # Result Ingestion
    # --------------------------------------------------------------------------

    def ingest_worker_result(
        self,
        result: WorkerResultRecord,
    ) -> Tuple[bool, str]:
        """Ingests a completed worker result with strict digest and execution binding."""
        with self._transaction():
            self._reconcile_transactions()
            queue_data = self.transport.read_json("task_queue.json") or {"tasks": {}}
            tasks = queue_data.get("tasks", {})
            lease_data = self.transport.read_json("active_leases.json") or {"leases": {}}
            leases = lease_data.get("leases", {})
            reg_data = self.transport.read_json("node_registry.json") or {"nodes": {}}
            nodes = reg_data.get("nodes", {})

            # 1. Validate Task exists
            if result.task_id not in tasks:
                return False, f"Task {result.task_id} not found in task queue"
            task_dict = tasks[result.task_id]

            # Compute canonical immutable digest
            res_digest = compute_result_digest(result)

            # 2. Check Strict Idempotency for already-completed task
            if task_dict.get("status") == "COMPLETE":
                is_identical = (
                    task_dict.get("result_id") == result.result_id
                    and task_dict.get("result_digest") == res_digest
                    and task_dict.get("accepted_node_id") == result.node_id
                    and task_dict.get("accepted_lease_id") == result.lease_id
                )
                if is_identical:
                    return True, "Duplicate identical result accepted idempotently"
                return False, (
                    f"Conflicting or altered second result {result.result_id} "
                    f"rejected for already-completed task {result.task_id}"
                )

            # 3. Validate Lease exists
            if result.lease_id not in leases:
                return False, f"Lease {result.lease_id} not found in active leases"
            lease_dict = leases[result.lease_id]

            # 4. Strict matching: task_id, node_id, lease_id
            if lease_dict.get("task_id") != result.task_id:
                return False, (
                    f"Mismatched task_id: result has {result.task_id}, "
                    f"lease {result.lease_id} is for {lease_dict.get('task_id')}"
                )
            if lease_dict.get("node_id") != result.node_id:
                return False, (
                    f"Mismatched node_id: result submitted by {result.node_id}, "
                    f"but lease owned by {lease_dict.get('node_id')}"
                )
            if lease_dict.get("status") not in ("ACTIVE", "EXPIRED_UNCERTAIN"):
                return False, f"Stale or released lease {result.lease_id} (status: {lease_dict.get('status')})"

            # 5. Persist Result with Digest
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            res_dict = asdict(result)
            res_dict["result_digest"] = res_digest
            res_file = f"results/{result.result_id}.json"
            self.transport.write_json(res_file, res_dict)

            # 6. Release Authoritative Lease & Scope Locks
            lease_dict["status"] = "RELEASED"
            self.transport.write_json("active_leases.json", lease_data)

            # 7. Update Task
            task_dict["status"] = "COMPLETE" if result.status == "SUCCESS" else "FAILED_SAFE"
            task_dict["result_id"] = result.result_id
            task_dict["result_digest"] = res_digest
            task_dict["accepted_node_id"] = result.node_id
            task_dict["accepted_lease_id"] = result.lease_id
            task_dict["lease_owner"] = None
            task_dict["lease_id"] = None
            task_dict["lease_expires_at"] = None
            self.transport.write_json("task_queue.json", queue_data)

            # 8. Update Node (strictly modifying ONLY lease_dict['node_id'])
            owner_node_id = lease_dict["node_id"]
            if owner_node_id in nodes:
                n_dict = nodes[owner_node_id]
                n_dict["current_task_id"] = None
                n_dict["current_lease_id"] = None
                n_dict["current_file_scope"] = []
                n_dict["heavy_job_active"] = False
                n_dict["last_result_id"] = result.result_id
                n_dict["status"] = result.next_state or "READY"
                self.transport.write_json("node_registry.json", reg_data)

            return True, f"Result {result.result_id} ingested successfully"

    # --------------------------------------------------------------------------
    # Restart Recovery
    # --------------------------------------------------------------------------

    def recover_after_restart(self) -> Dict[str, Any]:
        """Recovers dispatcher state after process restart without duplicating completed work."""
        with self._transaction():
            self._reconcile_transactions()
            stale_nodes = self.reconcile_stale_nodes()
            expired_leases = self.reconcile_expired_leases()
            active_leases = self.get_active_leases()
            ready_tasks = self.list_tasks(status="READY")
            completed_tasks = self.list_tasks(status="COMPLETE")
            reconciliation_tasks = self.list_tasks(status="RECONCILIATION_REQUIRED")

            return {
                "recovery_status": "RECOVERED",
                "stale_nodes_detected": stale_nodes,
                "expired_leases_reconciled": expired_leases,
                "active_leases_count": len(active_leases),
                "ready_tasks_count": len(ready_tasks),
                "completed_tasks_preserved_count": len(completed_tasks),
                "reconciliation_required_tasks_count": len(reconciliation_tasks),
            }

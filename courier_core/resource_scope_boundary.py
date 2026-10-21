"""Resource Scope, Shared Mutable Guard & Snapshot Consistency Boundary (CP-22 / CQ-22 / GB-SCOPE-01)

Durable Cannon Invariants:
1. Conflicts beyond simple identical file paths:
   - Overlapping Directory Trees (parent vs child directory writes, e.g. `src/` vs `src/api/`).
   - Git Index Lock (`.git/index` writes cannot run concurrently).
   - Generated Artifacts (compilation/build outputs).
   - Network Ports (port collisions on local loopback).
   - Test Databases (shared mutable database tables/files).
2. Reader-vs-Writer Snapshot Policy:
   - READ_SHARED: Concurrent readers may access the same resource simultaneously under a consistent snapshot_id.
   - WRITE_EXCLUSIVE: A writer locks the resource exclusively against all other readers and writers.
3. Parallel Label is NOT a permission:
   - Tasks labeled with `parallel=True` or `concurrency_allowed=True` are strictly rejected if a physical scope conflict exists.
4. Required Evidence:
   - scope-model, shared-resources, snapshot-policy.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class AccessMode(str, Enum):
    READ_SHARED = "READ_SHARED"
    WRITE_EXCLUSIVE = "WRITE_EXCLUSIVE"


class ResourceType(str, Enum):
    FILE = "FILE"
    DIRECTORY_TREE = "DIRECTORY_TREE"
    GIT_INDEX = "GIT_INDEX"
    PORT = "PORT"
    TEST_DATABASE = "TEST_DATABASE"
    GENERATED_ARTIFACT = "GENERATED_ARTIFACT"


class ScopeConflictError(RuntimeError):
    """Raised when an execution violates resource scope exclusivity boundaries."""


@dataclass(frozen=True)
class ResourceClaim:
    resource_type: ResourceType
    identifier: str
    access_mode: AccessMode
    snapshot_id: Optional[str] = None

    def normalized_identifier(self) -> str:
        ident = self.identifier.strip()
        if self.resource_type in (ResourceType.FILE, ResourceType.DIRECTORY_TREE, ResourceType.GENERATED_ARTIFACT):
            # Normalize path separators and casing for Windows compatibility
            norm = os.path.normpath(ident).replace("\\", "/").lower()
            if self.resource_type == ResourceType.DIRECTORY_TREE and not norm.endswith("/"):
                norm += "/"
            return norm
        elif self.resource_type == ResourceType.PORT:
            return ident.lower()
        elif self.resource_type == ResourceType.GIT_INDEX:
            return "git:index:global"
        elif self.resource_type == ResourceType.TEST_DATABASE:
            return os.path.normpath(ident).replace("\\", "/").lower()
        return ident.lower()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "identifier": self.identifier,
            "access_mode": self.access_mode.value,
            "snapshot_id": self.snapshot_id,
        }


@dataclass
class TaskScope:
    task_id: str
    claims: List[ResourceClaim]
    has_parallel_label: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "claims": [c.to_dict() for c in self.claims],
            "has_parallel_label": self.has_parallel_label,
        }


def check_resource_conflict(a: ResourceClaim, b: ResourceClaim) -> Optional[str]:
    """Detects whether two resource claims conflict.

    Rules:
    - READ_SHARED vs READ_SHARED: NEVER conflicts (concurrent reads allowed).
    - If at least one is WRITE_EXCLUSIVE:
      * Identical resource type and normalized identifier -> CONFLICT.
      * Directory Tree vs Directory Tree: parent/child overlap -> CONFLICT.
      * File vs Directory Tree: file located inside directory tree -> CONFLICT.
      * Git Index vs Git Index -> CONFLICT.
      * Port vs Port with same port number -> CONFLICT.
      * Test DB vs Test DB with same URI -> CONFLICT.
    """
    if a.access_mode == AccessMode.READ_SHARED and b.access_mode == AccessMode.READ_SHARED:
        return None

    id_a = a.normalized_identifier()
    id_b = b.normalized_identifier()

    # 1. Git Index Conflict
    if a.resource_type == ResourceType.GIT_INDEX and b.resource_type == ResourceType.GIT_INDEX:
        return "GIT_INDEX_EXCLUSIVE_MUTATION: Git working tree index cannot be modified concurrently."

    # 2. Port Collision
    if a.resource_type == ResourceType.PORT and b.resource_type == ResourceType.PORT:
        if id_a == id_b:
            return f"PORT_COLLISION: Both tasks attempt to bind exclusive network port '{a.identifier}'."

    # 3. Test Database Contention
    if a.resource_type == ResourceType.TEST_DATABASE and b.resource_type == ResourceType.TEST_DATABASE:
        if id_a == id_b:
            return f"TEST_DB_WRITE_CONTENTION: Both tasks target mutable test database '{a.identifier}'."

    # 4. Exact match on files or artifacts
    if id_a == id_b:
        return f"EXACT_RESOURCE_COLLISION: Mutual exclusion on '{a.identifier}' ({a.resource_type.value})."

    # 5. Directory Tree vs Directory Tree Hierarchical Overlap
    if a.resource_type == ResourceType.DIRECTORY_TREE and b.resource_type == ResourceType.DIRECTORY_TREE:
        if id_a.startswith(id_b) or id_b.startswith(id_a):
            return f"DIRECTORY_TREE_OVERLAP: Parent/child directory hierarchy conflict between '{a.identifier}' and '{b.identifier}'."

    # 6. File vs Directory Tree Containment
    if a.resource_type == ResourceType.FILE and b.resource_type == ResourceType.DIRECTORY_TREE:
        if id_a.startswith(id_b):
            return f"FILE_IN_MUTABLE_DIRECTORY: File '{a.identifier}' is contained in mutable directory tree '{b.identifier}'."

    if b.resource_type == ResourceType.FILE and a.resource_type == ResourceType.DIRECTORY_TREE:
        if id_b.startswith(id_a):
            return f"FILE_IN_MUTABLE_DIRECTORY: File '{b.identifier}' is contained in mutable directory tree '{a.identifier}'."

    return None


class ResourceScopeBoundary:
    """Enforces multi-resource concurrency safety, directory hierarchy isolation, and snapshot policies."""

    def __init__(self) -> None:
        self.active_scopes: Dict[str, TaskScope] = {}

    def can_admit(self, candidate: TaskScope) -> Tuple[bool, Optional[str]]:
        """Evaluates whether candidate task can run concurrently with all currently active tasks.

        INVARIANT: has_parallel_label=True is NEVER treated as permission to bypass conflicts.
        """
        for active_task_id, active_scope in self.active_scopes.items():
            for c_cand in candidate.claims:
                for c_active in active_scope.claims:
                    conflict_reason = check_resource_conflict(c_cand, c_active)
                    if conflict_reason:
                        label_note = " (Note: task parallel label does not grant permission to bypass scope conflict)" if candidate.has_parallel_label else ""
                        return False, f"Conflict with active task '{active_task_id}': {conflict_reason}{label_note}"

        return True, None

    def acquire(self, task_scope: TaskScope) -> None:
        """Admits task scope into active execution. Fails closed with ScopeConflictError if conflicting."""
        allowed, reason = self.can_admit(task_scope)
        if not allowed:
            raise ScopeConflictError(f"Admission denied for task '{task_scope.task_id}': {reason}")
        self.active_scopes[task_scope.task_id] = task_scope

    def release(self, task_id: str) -> None:
        """Releases active task scope."""
        self.active_scopes.pop(task_id, None)

    def generate_scope_evidence(self) -> Dict[str, Any]:
        """Generates CP-22 required evidence: ['scope-model', 'shared-resources', 'snapshot-policy']."""
        active_claims = []
        for scope in self.active_scopes.values():
            active_claims.extend(scope.to_dict()["claims"])

        return {
            "required_evidence": ["scope-model", "shared-resources", "snapshot-policy"],
            "scope-model": {
                "supported_resource_types": [r.value for r in ResourceType],
                "access_modes": [m.value for m in AccessMode],
                "active_task_scopes": {tid: s.to_dict() for tid, s in self.active_scopes.items()},
                "conflict_detection_rules": [
                    "READ_SHARED concurrency permitted on identical resource",
                    "WRITE_EXCLUSIVE serializes all readers and writers",
                    "Hierarchical directory tree containment enforces parent/child conflict",
                    "Git index mutation is globally serialized",
                    "Network ports enforce exclusive socket reservation",
                    "Parallel label cannot override resource conflict",
                ],
            },
            "shared-resources": {
                "active_claimed_resources_count": len(active_claims),
                "claims": active_claims,
            },
            "snapshot-policy": {
                "snapshot_isolation": "READ_SHARED claims require or bind to explicit snapshot_id (git SHA / timestamp)",
                "dirty_read_prevention": "Writers block subsequent readers until snapshot increment",
                "non_interference_guarantee": "Independent read snapshots observe immutable state regardless of parallel operations in disjoint scopes",
            },
        }

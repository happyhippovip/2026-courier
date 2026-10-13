"""Capsule schema: reusable work package, no private project data."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

SCHEMA_VERSION = "capsule/v1"
LICENSE_ALLOWLIST = frozenset({"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "CC0-1.0"})
MAX_CAPSULE_BYTES = 256 * 1024

REQUIRED_FIELDS = ("capsule_id", "version", "author", "license", "task_class", "problem_class",
                   "inputs", "planning_pattern", "worker_requirements", "verification_pattern",
                   "failure_modes", "cost_profile", "output_schema")


class CapsuleStatus(str, Enum):
    QUARANTINED = "quarantined"
    APPROVED = "approved"      # independent review passed + human gate
    REJECTED = "rejected"
    RECALLED = "recalled"


@dataclass
class Capsule:
    capsule_id: str
    version: str
    author: str
    license: str
    task_class: str
    problem_class: str
    inputs: Dict[str, Any]
    planning_pattern: List[str]
    worker_requirements: Dict[str, Any]
    verification_pattern: List[str]
    failure_modes: List[str]
    cost_profile: Dict[str, Any]
    output_schema: Dict[str, Any]
    code: Dict[str, str] = field(default_factory=dict)  # filename -> python source (optional helpers)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def key(self) -> str:
        return f"{self.capsule_id}@{self.version}"

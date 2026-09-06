"""Courier Experience Memory: Persists sanitized learning records from verified goal execution.

Contract:
- GOAL
- TASK
- RESULT
- ERROR (if any)
- ROOT_CAUSE
- LESSON
- REUSABLE_PATTERN
- FINGERPRINT
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.courier_safety_dispatcher import canonical_hash, write_json_atomic


@dataclass(frozen=True)
class ExperienceMemoryRecord:
    memory_id: str
    goal: str
    task: Dict[str, Any]
    result: Dict[str, Any]
    error: Optional[str]
    root_cause: Optional[str]
    lesson: str
    reusable_pattern: str
    fingerprint: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "memory_id": self.memory_id,
            "goal": self.goal,
            "task": self.task,
            "result": self.result,
            "error": self.error,
            "root_cause": self.root_cause,
            "lesson": self.lesson,
            "reusable_pattern": self.reusable_pattern,
            "fingerprint": self.fingerprint,
            "timestamp": self.timestamp,
        }


class CourierExperienceMemory:
    """Persists and queries experience memory records across autonomous cycles."""

    def __init__(self, workspace_dir: str | Path):
        self.workspace_dir = Path(workspace_dir)
        self.memory_dir = self.workspace_dir / "events" / "experience-memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def record_learning(
        self,
        goal: str,
        task: Dict[str, Any],
        result: Dict[str, Any],
        error: Optional[str] = None,
        root_cause: Optional[str] = None,
        lesson: str = "",
        reusable_pattern: str = "",
    ) -> Dict[str, Any]:
        """Persists a sanitized learning memory record."""
        sanitized_task = {k: v for k, v in task.items() if not any(s in k.lower() for s in ("token", "key", "secret", "auth"))}
        sanitized_result = {k: v for k, v in result.items() if not any(s in k.lower() for s in ("token", "key", "secret", "auth"))}

        fp_payload = {
            "goal": goal,
            "task": sanitized_task,
            "result": sanitized_result,
            "lesson": lesson,
            "reusable_pattern": reusable_pattern,
        }
        fp = canonical_hash(fp_payload)
        mem_id = f"mem-{uuid.uuid4().hex[:12]}"

        record = {
            "schema_version": "1.0",
            "memory_id": mem_id,
            "goal": goal,
            "task": sanitized_task,
            "result": sanitized_result,
            "error": error,
            "root_cause": root_cause,
            "lesson": lesson,
            "reusable_pattern": reusable_pattern,
            "fingerprint": fp,
            "timestamp": time.time(),
        }

        out_file = self.memory_dir / f"{mem_id}.json"
        write_json_atomic(out_file, record)
        return record

    def list_memories(self) -> List[Dict[str, Any]]:
        """Returns all persisted memory records sorted by timestamp."""
        records = []
        for file in sorted(self.memory_dir.glob("mem-*.json")):
            try:
                records.append(json.loads(file.read_text(encoding="utf-8")))
            except Exception:
                continue
        return records

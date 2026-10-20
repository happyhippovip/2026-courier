"""Worker Capability Matrix and Hardware/Software Tag Matcher (P28)

Provides fail-closed worker matching against work item execution requirements,
verifying operating system, hardware architecture, required/forbidden tags,
resource constraints (memory, CPU, current load), and provider support.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkerCapabilities:
    worker_id: str
    os: str
    arch: str
    tags: Dict[str, Any] = field(default_factory=dict)
    supported_providers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "os": self.os,
            "arch": self.arch,
            "tags": dict(self.tags),
            "supported_providers": list(self.supported_providers),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerCapabilities:
        return cls(
            worker_id=str(data.get("worker_id", "")),
            os=str(data.get("os", "")).lower(),
            arch=str(data.get("arch", "")).lower(),
            tags=dict(data.get("tags", {})),
            supported_providers=[str(p) for p in data.get("supported_providers", [])],
        )


@dataclass
class TaskRequirements:
    work_item_id: str
    required_os: Optional[str] = None
    required_arch: Optional[str] = None
    required_tags: Dict[str, Any] = field(default_factory=dict)
    forbidden_tags: List[str] = field(default_factory=list)
    min_memory_mb: Optional[int] = None
    min_cpu_cores: Optional[int] = None
    max_load: Optional[float] = None
    required_provider: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_item_id": self.work_item_id,
            "required_os": self.required_os,
            "required_arch": self.required_arch,
            "required_tags": dict(self.required_tags),
            "forbidden_tags": list(self.forbidden_tags),
            "min_memory_mb": self.min_memory_mb,
            "min_cpu_cores": self.min_cpu_cores,
            "max_load": self.max_load,
            "required_provider": self.required_provider,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskRequirements:
        return cls(
            work_item_id=str(data.get("work_item_id", "")),
            required_os=data.get("required_os"),
            required_arch=data.get("required_arch"),
            required_tags=dict(data.get("required_tags", {})),
            forbidden_tags=[str(t) for t in data.get("forbidden_tags", [])],
            min_memory_mb=data.get("min_memory_mb"),
            min_cpu_cores=data.get("min_cpu_cores"),
            max_load=data.get("max_load"),
            required_provider=data.get("required_provider"),
        )


@dataclass
class MatchResult:
    matched: bool
    score: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched": self.matched,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass
class CandidateWorker:
    worker: WorkerCapabilities
    score: float
    match_result: MatchResult


def match_capabilities(worker: WorkerCapabilities, req: TaskRequirements) -> MatchResult:
    """Evaluate whether a worker satisfies the task execution requirements."""
    reasons: List[str] = []

    # 1. OS check
    if req.required_os:
        if worker.os.lower() != req.required_os.lower():
            reasons.append(
                f"OS mismatch: required '{req.required_os}', worker has '{worker.os}'"
            )

    # 2. Architecture check
    if req.required_arch:
        if worker.arch.lower() != req.required_arch.lower():
            reasons.append(
                f"Architecture mismatch: required '{req.required_arch}', worker has '{worker.arch}'"
            )

    # 3. Required tags
    for tag_name, expected_val in req.required_tags.items():
        if tag_name not in worker.tags:
            reasons.append(f"Missing required tag '{tag_name}'")
        elif worker.tags[tag_name] != expected_val:
            reasons.append(
                f"Tag value mismatch for '{tag_name}': expected {expected_val}, got {worker.tags[tag_name]}"
            )

    # 4. Forbidden tags
    for tag_name in req.forbidden_tags:
        if tag_name in worker.tags and bool(worker.tags[tag_name]):
            reasons.append(f"Forbidden tag '{tag_name}' is present on worker")

    # 5. Resource constraints: memory
    if req.min_memory_mb is not None:
        actual_mem = worker.tags.get("memory_mb", 0)
        if actual_mem < req.min_memory_mb:
            reasons.append(
                f"Insufficient memory: required {req.min_memory_mb}MB, worker has {actual_mem}MB"
            )

    # 6. Resource constraints: CPU cores
    if req.min_cpu_cores is not None:
        actual_cpu = worker.tags.get("cpu_cores", 0)
        if actual_cpu < req.min_cpu_cores:
            reasons.append(
                f"Insufficient CPU cores: required {req.min_cpu_cores}, worker has {actual_cpu}"
            )

    # 7. Current load limit
    if req.max_load is not None:
        actual_load = worker.tags.get("current_load", 0.0)
        if actual_load > req.max_load:
            reasons.append(
                f"Load exceeds limit: max {req.max_load}, worker has {actual_load}"
            )

    # 8. Provider support
    if req.required_provider:
        if req.required_provider not in worker.supported_providers:
            reasons.append(
                f"Provider '{req.required_provider}' not supported by worker"
            )

    if reasons:
        return MatchResult(matched=False, score=0.0, reasons=reasons)

    # Calculate affinity / fitness score
    score = 100.0
    mem_mb = float(worker.tags.get("memory_mb", 0))
    score += (mem_mb / 1024.0) * 2.0
    load = float(worker.tags.get("current_load", 0.5))
    score += (1.0 - min(max(load, 0.0), 1.0)) * 50.0
    cpu = float(worker.tags.get("cpu_cores", 1))
    score += cpu * 5.0
    score += len(worker.tags) * 5.0

    return MatchResult(matched=True, score=round(score, 2), reasons=["All requirements satisfied"])


class CapabilityRegistry:
    """In-memory or persisted registry of workers and their capabilities."""

    def __init__(self) -> None:
        self._workers: Dict[str, WorkerCapabilities] = {}

    def register(self, worker: WorkerCapabilities) -> None:
        self._workers[worker.worker_id] = worker

    def unregister(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)

    def get_worker(self, worker_id: str) -> Optional[WorkerCapabilities]:
        return self._workers.get(worker_id)

    def list_workers(self) -> List[WorkerCapabilities]:
        return list(self._workers.values())

    def find_matching_workers(self, req: TaskRequirements) -> List[CandidateWorker]:
        candidates: List[CandidateWorker] = []
        for worker in self._workers.values():
            result = match_capabilities(worker, req)
            if result.matched:
                candidates.append(CandidateWorker(worker=worker, score=result.score, match_result=result))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Worker Capability Matcher CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match", help="Match a worker against a task requirement")
    match_parser.add_argument("--worker", required=True, help="Path to worker capabilities JSON")
    match_parser.add_argument("--task", required=True, help="Path to task requirements JSON")

    args = parser.parse_args(argv)

    if args.command == "match":
        worker_data = json.loads(Path(args.worker).read_text(encoding="utf-8"))
        task_data = json.loads(Path(args.task).read_text(encoding="utf-8"))

        worker = WorkerCapabilities.from_dict(worker_data)
        req = TaskRequirements.from_dict(task_data)

        result = match_capabilities(worker, req)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.matched else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

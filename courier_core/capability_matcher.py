"""Worker Capability Matrix, Router, and Decoupled Vocabulary (CP-16 / P16)

Provides fail-closed worker matching against work item execution requirements,
strictly decoupling:
1. Physical Platform / OS (windows, macos, linux, generic)
2. Execution Capabilities (python, powershell, bash, deterministic_ci, verifier, etc.)
3. Provider Preference & Runtimes (antigravity, github, codex, local, etc.)

Acceptance Invariants:
- Generic work remains platform-neutral (runs on Windows, macOS, or Linux).
- Genuine macOS / Windows requirements remain strictly enforced.
- Unqualified workers are fail-closed excluded.
- Antigravity is a provider runtime, NOT coupled to macOS.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class PlatformVocabulary:
    """Canonical physical operating system and platform identifiers."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    GENERIC = "generic"


class CapabilityVocabulary:
    """Canonical functional capability identifiers."""
    PYTHON = "python"
    GIT = "git"
    POWERSHELL = "powershell"
    BASH = "bash"
    DETERMINISTIC_CI = "deterministic_ci"
    STRONG_CODE = "strong_code"
    VERIFIER = "verifier"
    HUMAN = "human"
    DOCKER = "docker"


class ProviderVocabulary:
    """Canonical agent provider and runtime environment identifiers."""
    ANTIGRAVITY = "antigravity"
    GITHUB = "github"
    CODEX = "codex"
    LOCAL_DETERMINISTIC = "local_deterministic"
    MUSE = "muse"
    GEMINI = "gemini"


KNOWN_PROVIDERS: Set[str] = {
    ProviderVocabulary.ANTIGRAVITY,
    ProviderVocabulary.GITHUB,
    ProviderVocabulary.CODEX,
    ProviderVocabulary.LOCAL_DETERMINISTIC,
    ProviderVocabulary.MUSE,
    ProviderVocabulary.GEMINI,
    "local",
    "mock",
}


@dataclass
class WorkerCapabilities:
    worker_id: str
    os: str
    arch: str = "x86_64"
    tags: Dict[str, Any] = field(default_factory=dict)
    supported_providers: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "os": self.os,
            "arch": self.arch,
            "tags": dict(self.tags),
            "supported_providers": list(self.supported_providers),
            "capabilities": list(self.capabilities),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerCapabilities:
        raw_caps = data.get("capabilities", [])
        caps = [str(c).strip().lower() for c in raw_caps]
        raw_providers = data.get("supported_providers", [])
        providers = [str(p).strip().lower() for p in raw_providers]
        # Infer any known providers declared in capabilities for backward compatibility
        for c in caps:
            if c in KNOWN_PROVIDERS and c not in providers:
                providers.append(c)

        raw_os = str(data.get("os", data.get("platform", ""))).lower().strip()
        if not raw_os or raw_os in ("unknown", "worker"):
            for c in caps:
                if c in ("windows", "win", "win32"):
                    raw_os = PlatformVocabulary.WINDOWS
                    break
                elif c in ("macos", "mac", "darwin"):
                    raw_os = PlatformVocabulary.MACOS
                    break
                elif c == "linux":
                    raw_os = PlatformVocabulary.LINUX
                    break

        return cls(
            worker_id=str(data.get("worker_id", "")),
            os=raw_os,
            arch=str(data.get("arch", "x86_64")).lower().strip(),
            tags=dict(data.get("tags", {})),
            supported_providers=providers,
            capabilities=caps,
        )


@dataclass
class TaskRequirements:
    work_item_id: str
    required_os: Optional[str] = None
    required_arch: Optional[str] = None
    required_capabilities: List[str] = field(default_factory=list)
    required_provider: Optional[str] = None
    provider_preference: Optional[str] = None
    required_tags: Dict[str, Any] = field(default_factory=dict)
    forbidden_tags: List[str] = field(default_factory=list)
    min_memory_mb: Optional[int] = None
    min_cpu_cores: Optional[int] = None
    max_load: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_item_id": self.work_item_id,
            "required_os": self.required_os,
            "required_arch": self.required_arch,
            "required_capabilities": list(self.required_capabilities),
            "required_provider": self.required_provider,
            "provider_preference": self.provider_preference,
            "required_tags": dict(self.required_tags),
            "forbidden_tags": list(self.forbidden_tags),
            "min_memory_mb": self.min_memory_mb,
            "min_cpu_cores": self.min_cpu_cores,
            "max_load": self.max_load,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskRequirements:
        return cls(
            work_item_id=str(data.get("work_item_id", "")),
            required_os=data.get("required_os"),
            required_arch=data.get("required_arch"),
            required_capabilities=[str(c).strip().lower() for c in data.get("required_capabilities", [])],
            required_provider=data.get("required_provider"),
            provider_preference=data.get("provider_preference"),
            required_tags=dict(data.get("required_tags", {})),
            forbidden_tags=[str(t) for t in data.get("forbidden_tags", [])],
            min_memory_mb=data.get("min_memory_mb"),
            min_cpu_cores=data.get("min_cpu_cores"),
            max_load=data.get("max_load"),
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


def normalize_os(os_name: Optional[str]) -> Optional[str]:
    """Normalize OS identifier (mac/darwin -> macos, win/win32 -> windows)."""
    if not os_name:
        return None
    val = os_name.strip().lower()
    if val in ("darwin", "mac", "macos"):
        return PlatformVocabulary.MACOS
    if val in ("win", "win32", "windows"):
        return PlatformVocabulary.WINDOWS
    if val in ("linux", "posix"):
        return PlatformVocabulary.LINUX
    if val in ("any", "generic", "neutral", "*", "none"):
        return None
    return val


def match_capabilities(worker: WorkerCapabilities, req: TaskRequirements) -> MatchResult:
    """Evaluate whether a worker satisfies task execution requirements.
    
    Strictly separates:
    1. Physical Platform / OS
    2. Execution Capabilities
    3. Provider Preference & Runtimes
    """
    reasons: List[str] = []

    # 1. OS check: Generic / neutral tasks are platform-neutral
    norm_req_os = normalize_os(req.required_os)
    if norm_req_os is not None:
        norm_worker_os = normalize_os(worker.os)
        if norm_worker_os != norm_req_os:
            reasons.append(
                f"OS mismatch: required '{req.required_os}', worker has '{worker.os}'"
            )

    # 2. Architecture check
    if req.required_arch:
        req_arch = req.required_arch.strip().lower()
        if req_arch not in ("any", "generic", "*", ""):
            if worker.arch.strip().lower() != req_arch:
                reasons.append(
                    f"Architecture mismatch: required '{req.required_arch}', worker has '{worker.arch}'"
                )

    # 3. Required capabilities check
    worker_caps = {c.strip().lower() for c in worker.capabilities}
    worker_caps.update(str(k).strip().lower() for k in worker.tags.keys())
    for cap in req.required_capabilities:
        if cap.strip().lower() not in worker_caps:
            reasons.append(f"Missing required capability '{cap}'")

    # 4. Required tags
    for tag_name, expected_val in req.required_tags.items():
        if tag_name not in worker.tags:
            reasons.append(f"Missing required tag '{tag_name}'")
        elif worker.tags[tag_name] != expected_val:
            reasons.append(
                f"Tag value mismatch for '{tag_name}': expected {expected_val}, got {worker.tags[tag_name]}"
            )

    # 5. Forbidden tags
    for tag_name in req.forbidden_tags:
        if tag_name in worker.tags and bool(worker.tags[tag_name]):
            reasons.append(f"Forbidden tag '{tag_name}' is present on worker")

    # 6. Resource constraints: memory
    if req.min_memory_mb is not None:
        actual_mem = worker.tags.get("memory_mb", 0)
        if actual_mem < req.min_memory_mb:
            reasons.append(
                f"Insufficient memory: required {req.min_memory_mb}MB, worker has {actual_mem}MB"
            )

    # 7. Resource constraints: CPU cores
    if req.min_cpu_cores is not None:
        actual_cpu = worker.tags.get("cpu_cores", 0)
        if actual_cpu < req.min_cpu_cores:
            reasons.append(
                f"Insufficient CPU cores: required {req.min_cpu_cores}, worker has {actual_cpu}"
            )

    # 8. Current load limit
    if req.max_load is not None:
        actual_load = worker.tags.get("current_load", 0.0)
        if actual_load > req.max_load:
            reasons.append(
                f"Load exceeds limit: max {req.max_load}, worker has {actual_load}"
            )

    # 9. Provider support (strict constraint when required)
    worker_providers = {p.strip().lower() for p in worker.supported_providers}
    worker_providers.update(worker_caps)
    if req.required_provider:
        req_p = req.required_provider.strip().lower()
        if req_p not in worker_providers:
            reasons.append(
                f"Provider '{req.required_provider}' not supported by worker"
            )

    if reasons:
        return MatchResult(matched=False, score=0.0, reasons=reasons)

    # Calculate affinity / fitness score
    score = 100.0

    # Soft Provider Preference Bonus
    if req.provider_preference:
        pref = req.provider_preference.strip().lower()
        if pref in worker_providers:
            score += 50.0

    mem_mb = float(worker.tags.get("memory_mb", 0))
    score += (mem_mb / 1024.0) * 2.0
    load = float(worker.tags.get("current_load", 0.5))
    score += (1.0 - min(max(load, 0.0), 1.0)) * 50.0
    cpu = float(worker.tags.get("cpu_cores", 1))
    score += cpu * 5.0
    score += len(worker.tags) * 5.0

    return MatchResult(matched=True, score=round(score, 2), reasons=["All requirements satisfied"])


def parse_task_routing(data: Dict[str, Any]) -> TaskRequirements:
    """Extract and decouple TaskRequirements from a task dictionary.
    
    Resolves legacy `target_agent` strings without false semantic coupling:
    - "antigravity" sets required_provider="antigravity" (platform-neutral).
    - "github" sets required_provider="github" (platform-neutral).
    - "windows" sets required_os="windows".
    - "mac" / "macos" sets required_os="macos".
    - "linux" sets required_os="linux".
    - "generic" / "any" sets required_os=None (platform-neutral).
    
    Explicit fields (`required_os`, `required_provider`, `provider_preference`,
    `required_capabilities`) always take precedence over legacy string parsing.
    """
    task_id = str(data.get("task_id", data.get("work_item_id", "")))
    req_os = data.get("required_os")
    req_provider = data.get("required_provider")
    pref_provider = data.get("provider_preference")
    req_caps = list(data.get("required_capabilities", []))

    # Resolve legacy target_agent if explicit fields are omitted
    target = str(data.get("target_agent", "")).strip().lower()
    if target and target not in ("none", ""):
        if target in ("generic", "any", "neutral", "all"):
            if req_os is None:
                req_os = None
        elif target in ("windows", "win", "win32"):
            if req_os is None:
                req_os = PlatformVocabulary.WINDOWS
        elif target in ("mac", "macos", "darwin"):
            if req_os is None:
                req_os = PlatformVocabulary.MACOS
        elif target == "linux":
            if req_os is None:
                req_os = PlatformVocabulary.LINUX
        elif target == "antigravity":
            # Semantic decoupling: Antigravity is an agent provider, NOT an OS requirement!
            if req_provider is None:
                req_provider = ProviderVocabulary.ANTIGRAVITY
        elif target == "github":
            if req_provider is None:
                req_provider = ProviderVocabulary.GITHUB
        elif target == "codex":
            if req_provider is None:
                req_provider = ProviderVocabulary.CODEX
        elif target == "muse":
            if req_provider is None:
                req_provider = ProviderVocabulary.MUSE

    # Also inspect platform field if present
    platform = data.get("platform")
    if platform and req_os is None:
        norm_p = normalize_os(str(platform))
        if norm_p is not None:
            req_os = norm_p

    return TaskRequirements(
        work_item_id=task_id,
        required_os=req_os,
        required_arch=data.get("required_arch"),
        required_capabilities=req_caps,
        required_provider=req_provider,
        provider_preference=pref_provider,
        required_tags=dict(data.get("required_tags", {})),
        forbidden_tags=list(data.get("forbidden_tags", [])),
        min_memory_mb=data.get("min_memory_mb"),
        min_cpu_cores=data.get("min_cpu_cores"),
        max_load=data.get("max_load"),
    )


def parse_worker_capabilities(data: Dict[str, Any]) -> WorkerCapabilities:
    """Parse a registered worker record into WorkerCapabilities."""
    return WorkerCapabilities.from_dict(data)


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

"""Quota-blocked lane hibernation (Issue #75, MAC03 provider continuity).

Real incident: a provider quota exhaustion left local sessions, watchers,
and UI/PTY resources consuming host capacity while the lane could do no
provider work. A quota-blocked/idle lane must instead:

    checkpoint -> release unnecessary provider/UI/PTY resources -> HIBERNATED

Rules enforced here:

- hibernate only when no LOCAL_READY work remains, every provider circuit
  for the lane is OPEN, and no authorized fallback exists;
- Human Desk / authority-gated resources are essential and are never
  released;
- the checkpoint carries the canonical continuation fields from Issue #75
  so restart reconstructs lane truth deterministically;
- resume restores exactly the checkpointed truth, never a guessed one.
"""

import enum
import json
import os
from pathlib import Path
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class LaneState(enum.Enum):
    ACTIVE = "ACTIVE"
    HIBERNATED = "HIBERNATED"


# Resource kinds that are safe to release while hibernated. Anything not
# listed here (notably human_desk) is treated as essential.
RELEASABLE_KINDS = frozenset({"provider", "watcher", "ui", "pty"})


@dataclass
class Resource:
    name: str
    kind: str
    essential: bool = False
    released: bool = False


@dataclass
class ContinuationCheckpoint:
    """Canonical continuation packet persisted before hibernation."""

    project: str = "Courier"
    role: str = "PROVIDER_CONTINUITY"
    stage: str = ""
    repo_sha: str = ""
    branch: str = ""
    pr: str = ""
    task_id: str = ""
    attempt: int = 1
    dispatch_id: str = ""
    effect_key: str = ""
    completed_fingerprints: List[str] = field(default_factory=list)
    open_local_units: List[str] = field(default_factory=list)
    open_provider_units: List[str] = field(default_factory=list)
    latest_tests: str = ""
    provider_failure_class: str = ""
    provider_reset_time: Optional[str] = None
    authority_boundary: str = "PRESERVED"
    next_units: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    workkey: str = ""
    mutable_scope: str = ""
    next_action: str = ""
    provider_connection_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "role": self.role,
            "stage": self.stage,
            "repo_sha": self.repo_sha,
            "branch": self.branch,
            "pr": self.pr,
            "task_id": self.task_id,
            "attempt": self.attempt,
            "dispatch_id": self.dispatch_id,
            "effect_key": self.effect_key,
            "completed_fingerprints": list(self.completed_fingerprints),
            "open_local_units": list(self.open_local_units),
            "open_provider_units": list(self.open_provider_units),
            "latest_tests": self.latest_tests,
            "provider_failure_class": self.provider_failure_class,
            "provider_reset_time": self.provider_reset_time,
            "authority_boundary": self.authority_boundary,
            "next_units": list(self.next_units),
            "source_refs": list(self.source_refs),
            "workkey": self.workkey,
            "mutable_scope": self.mutable_scope,
            "next_action": self.next_action,
            "provider_connection_id": self.provider_connection_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContinuationCheckpoint":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def should_hibernate(
    open_local_units: List[str],
    open_provider_units: List[str],
    circuits_open: bool,
    fallback_available: bool,
) -> bool:
    """True only for a genuinely quota-blocked/idle lane.

    Never hibernate while LOCAL_READY work remains, while any provider
    circuit still admits traffic, or while an authorized fallback could
    continue provider-required units. Hibernating then would strand useful
    work; staying awake with nothing to do wastes host resources.
    """
    if open_local_units:
        return False
    if not open_provider_units:
        return False
    if not circuits_open:
        return False
    if fallback_available:
        return False
    return True


class LaneHibernator:
    """Checkpoint + release + HIBERNATED for one quota-blocked lane."""

    def __init__(self):
        self.state: LaneState = LaneState.ACTIVE
        self.resources: Dict[str, Resource] = {}
        self.release_hooks: Dict[str, Callable[[str], None]] = {}
        self.reacquire_hooks: Dict[str, Callable[[str], None]] = {}
        self.checkpoint: Optional[ContinuationCheckpoint] = None
        self.release_report: Dict[str, Any] = {}
        self.resume_report: Dict[str, Any] = {}

    def register_resource(
        self,
        name: str,
        kind: str,
        essential: bool = False,
        release_hook: Optional[Callable[[str], None]] = None,
        reacquire_hook: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.resources[name] = Resource(name=name, kind=kind, essential=essential)
        if release_hook is not None:
            self.release_hooks[name] = release_hook
        if reacquire_hook is not None:
            self.reacquire_hooks[name] = reacquire_hook

    def _releasable(self, res: Resource) -> bool:
        if res.essential:
            return False
        return res.kind in RELEASABLE_KINDS

    def hibernate(self, checkpoint: ContinuationCheckpoint,
                  persist: Optional[Callable[[], None]] = None) -> Dict[str, Any]:
        self.checkpoint = checkpoint
        # Persist the continuation BEFORE releasing even the first resource.
        if persist is not None:
            persist()
        if self.state == LaneState.HIBERNATED:
            return dict(self.release_report)
        released: List[str] = []
        retained: List[str] = []
        failed: List[str] = []
        for res in self.resources.values():
            if self._releasable(res):
                hook = self.release_hooks.get(res.name)
                if hook is not None and not res.released:
                    try:
                        hook(res.name)
                    except Exception:
                        failed.append(res.name)
                        continue
                res.released = True
                released.append(res.name)
            else:
                retained.append(res.name)
        self.state = LaneState.ACTIVE if failed else LaneState.HIBERNATED
        self.release_report = {
            "released": sorted(released),
            "retained": sorted(retained),
            "checkpoint_tasks": [checkpoint.task_id],
            "failed": sorted(failed),
        }
        if persist is not None:
            persist()
        return dict(self.release_report)

    def resume(self) -> ContinuationCheckpoint:
        """Reacquire released resources and return the checkpoint.

        Never raises for a failing hook: failures are collected into
        resume_report (mirroring hibernate()'s failed[] accounting) and the
        lane stays HIBERNATED until everything is really reacquired.
        res.released flips to False only after its own hook succeeds, so a
        partial resume is never mistaken for a live lane. Callers that would
        execute provider work must check resume_report["failed"] first.
        """
        if self.state != LaneState.HIBERNATED:
            raise RuntimeError("lane is not HIBERNATED")
        if self.checkpoint is None:
            raise RuntimeError("no checkpoint to resume from")

        reacquired: List[str] = []
        failed: List[str] = []
        for res in self.resources.values():
            if not res.released:
                continue
            hook = self.reacquire_hooks.get(res.name)
            if hook is not None:
                try:
                    hook(res.name)
                except Exception:
                    failed.append(res.name)
                    continue
            res.released = False
            reacquired.append(res.name)
        self.resume_report = {
            "reacquired": sorted(reacquired),
            "failed": sorted(failed),
        }
        self.state = LaneState.ACTIVE if not failed else LaneState.HIBERNATED
        return self.checkpoint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
            "release_report": self.release_report,
            "resume_report": self.resume_report,
            "resources": {
                name: {
                    "kind": res.kind,
                    "essential": res.essential,
                    "released": res.released,
                }
                for name, res in self.resources.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LaneHibernator":
        lane = cls()
        lane.state = LaneState(data.get("state", "ACTIVE"))
        lane.release_report = dict(data.get("release_report", {}))
        lane.resume_report = dict(data.get("resume_report", {}))
        if data.get("checkpoint"):
            lane.checkpoint = ContinuationCheckpoint.from_dict(data["checkpoint"])
        for name, spec in (data.get("resources") or {}).items():
            lane.resources[name] = Resource(
                name=name,
                kind=spec.get("kind", "other"),
                essential=bool(spec.get("essential", False)),
                released=bool(spec.get("released", False)),
            )
        return lane


def save_continuation(path, value):
    """Atomic, fsynced snapshot. Caller holds the existing runtime home lock.

    This is state persistence, not a new scheduler/claim mechanism. Never put
    secrets in continuation packets. An invalid snapshot must fail closed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".continuation-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

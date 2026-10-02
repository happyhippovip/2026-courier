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
        self.checkpoint: Optional[ContinuationCheckpoint] = None
        self.release_report: Dict[str, Any] = {}

    def register_resource(
        self,
        name: str,
        kind: str,
        essential: bool = False,
        release_hook: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.resources[name] = Resource(name=name, kind=kind, essential=essential)
        if release_hook is not None:
            self.release_hooks[name] = release_hook

    def _releasable(self, res: Resource) -> bool:
        if res.essential:
            return False
        return res.kind in RELEASABLE_KINDS

    def hibernate(self, checkpoint: ContinuationCheckpoint) -> Dict[str, Any]:
        if self.state == LaneState.HIBERNATED:
            return dict(self.release_report)
            
        self.checkpoint = checkpoint
        
        released: List[str] = []
        retained: List[str] = []
        for res in self.resources.values():
            if self._releasable(res):
                hook = self.release_hooks.get(res.name)
                if hook is not None:
                    try:
                        hook(res.name)
                        res.released = True
                        released.append(res.name)
                    except Exception:
                        retained.append(res.name)
                else:
                    retained.append(res.name)
            else:
                retained.append(res.name)
                
        self.state = LaneState.HIBERNATED
        self.release_report = {
            "released": sorted(released),
            "retained": sorted(retained),
            "checkpoint_tasks": [checkpoint.task_id],
        }
        return dict(self.release_report)

    def resume(self) -> ContinuationCheckpoint:
        if self.state != LaneState.HIBERNATED:
            raise RuntimeError("lane is not HIBERNATED")
        if self.checkpoint is None:
            raise RuntimeError("no checkpoint to resume from")
        self.state = LaneState.ACTIVE
        # Re-acquire: reset released flags so resources can be re-registered.
        for res in self.resources.values():
            res.released = False
        return self.checkpoint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
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

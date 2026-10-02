"""Issue #76 slice: explicit resource budgets + lane hibernation.

Owns ONE thing: the budget envelope with an emergency reserve, and the
checkpoint-first hibernation plan for logical lanes. It reuses (never
duplicates or rewrites):

- ``scripts.resource_governor.HostPressureController.MAX_HEAVY_JOBS``
  (the machine-wide heavy limit; imported, asserted by test);
- ``scripts.host_capacity`` health vocabulary (read as input only).

Why this slice: the 2026-10-02 Mac incident was multi-factor, but one
mechanism is certain -- idle/quota-blocked lanes stayed PHYSICALLY alive
(PTYs, watchers, pollers) while only LOGICALLY waiting, so an
API-quiet night still burned CPU. This module turns "idle or
quota-blocked" into "checkpointed and hibernated, pollers stopped".

64 logical lanes != 64 local heavy processes: lanes are orchestration
entries; heavy local execution is capped at MAX_HEAVY_LOCAL_JOBS (1,
machine-wide) by the imported governor invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:  # Single source of truth; fall back only defensively.
    from scripts.resource_governor import HostPressureController  # type: ignore
    MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE = HostPressureController.MAX_HEAVY_JOBS
except Exception:  # pragma: no cover - defensive fallback
    MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE = 1

# -- lane states ---------------------------------------------------------------
ACTIVE = "ACTIVE"
IDLE = "IDLE"
QUOTA_BLOCKED = "QUOTA_BLOCKED"
WAITING_LONG = "WAITING_LONG"
HIBERNATED = "HIBERNATED"

LANE_STATES = (ACTIVE, IDLE, QUOTA_BLOCKED, WAITING_LONG, HIBERNATED)
HIBERNATE_ELIGIBLE = (IDLE, QUOTA_BLOCKED, WAITING_LONG)

# -- admission states ---------------------------------------------------------------
# What the current host may start: full (OPEN), light/deterministic only
# (LIGHT_ONLY), or nothing but the emergency checkpoint path (CLOSED).
OPEN = "OPEN"
LIGHT_ONLY = "LIGHT_ONLY"
CLOSED = "CLOSED"

_HEALTH_SEVERITY = ("HEALTHY", "PRESSURED", "DEGRADED", "RESOURCE_PAUSE",
                    "EMERGENCY")


def _normalize_health(health: str) -> str:
    """Mission or capacity state -> capacity health. Unknown -> raise.

    Accepts both mission states (NOMINAL/WATCH/RECOVERING, via
    mission_state_to_health) and capacity states (HEALTHY/.../EMERGENCY,
    which map to themselves). Anything else is fail-closed ValueError,
    never an optimistic default.
    """
    upper = str(health).upper()
    if upper in _MISSION_TO_HEALTH:
        return _MISSION_TO_HEALTH[upper]
    if upper in _MISSION_TO_HEALTH.values():
        return upper  # already a capacity state (e.g. HEALTHY)
    raise ValueError(f"unknown health state: {health!r}") from None


def admission_state(health: str) -> str:
    """Three-way admission for a (possibly mission-worded) health state.

    HEALTHY -> OPEN; PRESSURED/DEGRADED -> LIGHT_ONLY (no new heavy work,
    existing safe work may finish); RESOURCE_PAUSE/EMERGENCY -> CLOSED
    (checkpoint/reconciliation only). Unknown input raises.
    """
    normalized = _normalize_health(health)
    if normalized == "HEALTHY":
        return OPEN
    if normalized in ("PRESSURED", "DEGRADED"):
        return LIGHT_ONLY
    return CLOSED


# -- mission -> capacity health mapping ----------------------------------------
_MISSION_TO_HEALTH = {
    "NOMINAL": "HEALTHY",
    "WATCH": "PRESSURED",      # rising load: light only, like PRESSURED
    "RECOVERING": "RESOURCE_PAUSE",  # reconcile/checkpoint only until probed
    "PRESSURED": "PRESSURED",
    "DEGRADED": "DEGRADED",
    "RESOURCE_PAUSE": "RESOURCE_PAUSE",
    "EMERGENCY": "EMERGENCY",
}


def mission_state_to_health(state: str) -> str:
    """Map a mission host state onto capacity health. Unknown -> raise.

    Never defaults to a healthy state: an unmapped signal is a fail-closed
    ValueError, not an optimistic guess.
    """
    try:
        return _MISSION_TO_HEALTH[str(state).upper()]
    except KeyError:
        raise ValueError(f"unknown mission host state: {state!r}") from None


# -- host telemetry escalation ----------------------------------------------------
# Cheap local signals (memory/swap/disk) can only ESCALATE the health
# derived from the mission state, never clear it: disk free space is a
# supporting signal, not proof of health, and UNKNOWN telemetry must not
# be treated as healthy. Callers pass plain observed values (no psutil
# dependency here, so every branch stays deterministic under test).
DISK_FLOOR_GB = 2.0


def escalate_health(health: str, *, memory_pressure: str = "NOMINAL",
                    swap_paging: bool | None = None,
                    disk_free_gb: float | None = None) -> str:
    """Escalate-only health fold-in for memory/swap/disk signals.

    memory_pressure: NOMINAL | HIGH | CRITICAL | UNKNOWN. HIGH means at
    least PRESSURED, CRITICAL at least RESOURCE_PAUSE, UNKNOWN at least
    PRESSURED (unknown is not healthy). swap_paging=True means at least
    PRESSURED. disk_free_gb below DISK_FLOOR_GB means at least
    RESOURCE_PAUSE (checkpointing itself is at risk). The input health
    is normalized first (unknown input raises); the result is never
    healthier than the input.
    """
    normalized = _normalize_health(health)
    level = _HEALTH_SEVERITY.index(normalized)

    def require(min_health: str) -> None:
        nonlocal level
        level = max(level, _HEALTH_SEVERITY.index(min_health))

    mem = str(memory_pressure).upper()
    if mem == "CRITICAL":
        require("RESOURCE_PAUSE")
    elif mem in ("HIGH", "UNKNOWN"):
        require("PRESSURED")
    elif mem != "NOMINAL":
        raise ValueError(f"unknown memory pressure: {memory_pressure!r}")
    if swap_paging:
        require("PRESSURED")
    if disk_free_gb is not None and disk_free_gb < DISK_FLOOR_GB:
        require("RESOURCE_PAUSE")
    return _HEALTH_SEVERITY[level]


# -- budgets --------------------------------------------------------------------
class BudgetExceeded(RuntimeError):
    """Normal work does not fit without touching the emergency reserve."""


@dataclass
class Budget:
    """One resource envelope. ``reserved`` is for checkpoint/emergency only."""

    name: str
    limit: int
    reserved: int = 0
    used: int = 0

    def fits_normal(self, cost: int) -> bool:
        return self.used + cost <= self.limit - self.reserved

    def fits_emergency(self, cost: int) -> bool:
        return self.used + cost <= self.limit

    def charge(self, cost: int, emergency: bool = False) -> None:
        ok = self.fits_emergency(cost) if emergency else self.fits_normal(cost)
        if not ok:
            raise BudgetExceeded(
                f"{self.name}: cost {cost} exceeds "
                f"{'limit' if emergency else 'limit-minus-reserve'} "
                f"(used={self.used}, limit={self.limit}, reserved={self.reserved})"
            )
        self.used += cost

    def release(self, cost: int) -> None:
        self.used = max(0, self.used - cost)


# Declared per-admission costs by work class. Heavy is 1 by construction:
# the machine-wide single-flight invariant, not a tunable.
WORK_COSTS = {
    "HEAVY": {"heavy_jobs": 1, "spawn": 1},
    "LIGHT": {"light_workers": 1},
    "CHECKPOINT": {},  # reserve-eligible; charged via emergency path only
}


# Per-host envelopes: one machine class is not every machine. Heavy is
# NOT profiled -- the machine-wide single-flight invariant holds on a
# workstation exactly as on a weak laptop. Unknown profile raises.
PROFILES = {
    "low": {"light_workers": 3, "spawn": 4, "fd": 512,
            "provider_sessions": 2, "scheduler_wakes": 30},
    "normal": {"light_workers": 6, "spawn": 8, "fd": 1024,
               "provider_sessions": 4, "scheduler_wakes": 60},
    "workstation": {"light_workers": 10, "spawn": 12, "fd": 2048,
                    "provider_sessions": 6, "scheduler_wakes": 90},
}

_PROFILE_RESERVE = {"light_workers": 1, "spawn": 1, "fd": 64,
                    "provider_sessions": 1, "scheduler_wakes": 10}


def default_budgets(profile: str = "normal") -> dict[str, Budget]:
    """Fresh per-host budgets for one supervisor lifetime.

    ``profile`` is low | normal | workstation (conservative defaults; a
    weaker customer machine may show 64 lanes while admitting only a
    small safe subset). Heavy stays at MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE
    on every profile.
    """
    try:
        envelope = PROFILES[profile]
    except KeyError:
        raise ValueError(f"unknown budget profile: {profile!r}") from None
    budgets = {
        "heavy_jobs": Budget("heavy_jobs",
                             MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE, reserved=0),
    }
    for name, limit in envelope.items():
        budgets[name] = Budget(name, limit,
                               reserved=_PROFILE_RESERVE.get(name, 0))
    return budgets


def admit_work(budgets: dict[str, Budget], work_class: str,
               health: str, emergency: bool = False,
               cleanup_proven: bool = True) -> bool:
    """Charge every budget a work class needs; all-or-nothing, fail-closed.

    Admission is three-way (see admission_state): CLOSED admits only the
    emergency checkpoint path; LIGHT_ONLY admits everything except HEAVY;
    OPEN admits all work classes subject to budget fit. An unverified
    cleanup (cleanup_proven=False) blocks HEAVY until the release is
    proven, so a leaked worker tree can never be replaced blindly.
    Unknown health or work class raises instead of guessing.
    """
    costs = WORK_COSTS.get(work_class)
    if costs is None:
        raise ValueError(f"unknown work class: {work_class!r}")
    admission = admission_state(health)  # raises on unknown health
    if admission == CLOSED and not emergency:
        return False
    if admission == LIGHT_ONLY and work_class == "HEAVY" and not emergency:
        return False
    if not cleanup_proven and work_class == "HEAVY" and not emergency:
        return False
    charged: list[tuple[Budget, int]] = []
    try:
        for name, cost in costs.items():
            budget = budgets[name]
            budget.charge(cost, emergency=emergency)
            charged.append((budget, cost))
    except (BudgetExceeded, KeyError):
        for budget, cost in charged:
            budget.release(cost)
        return False
    return True


def release(budgets: dict[str, Budget], work_class: str) -> None:
    for name, cost in WORK_COSTS.get(work_class, {}).items():
        if name in budgets:
            budgets[name].release(cost)


# -- recovery hysteresis ----------------------------------------------------------
@dataclass
class RecoveryHysteresis:
    """No flapping out of RESOURCE_PAUSE/EMERGENCY on one good sample.

    Recovery is admitted only after ``required_healthy`` CONSECUTIVE
    healthy probes; any unhealthy probe resets the streak to zero. This
    is the staged-resume side of admission: admit +2, observe, admit
    more -- never a full-capacity burst on the first green sample.
    """

    required_healthy: int = 3
    _streak: int = 0

    def probe(self, healthy: bool) -> bool:
        """Feed one health probe; True once recovery is admitted."""
        if healthy:
            self._streak += 1
        else:
            self._streak = 0
        return self._streak >= self.required_healthy


# -- hibernation -----------------------------------------------------------------
@dataclass
class Lane:
    id: str
    state: str = IDLE


def plan_hibernation(lanes: list[Lane], health: str,
                     quota_exhausted: bool = False) -> dict:
    """Checkpoint-first hibernation plan. Exact lane ids only, never broad.

    - IDLE / QUOTA_BLOCKED / WAITING_LONG always hibernate (physical, not
      logical waiting), on any health.
    - Provider quota exhausted also stops pollers: an API-quiet night must
      be a cool night.
    - RESOURCE_PAUSE / EMERGENCY hibernate everything except the canonical
      checkpoint service.
    - Already-HIBERNATED lanes are left alone (idempotent).
    - A lane in an UNKNOWN state hibernates fail-closed (never kept
      physically alive on an unreadable state) and is reported under
      "unknown" so the owner can reclassify it.
    """
    hibernate: list[str] = []
    keep: list[str] = []
    unknown: list[str] = []
    for lane in lanes:
        if lane.state == HIBERNATED:
            continue
        if health in ("RESOURCE_PAUSE", "EMERGENCY"):
            hibernate.append(lane.id)
        elif lane.state in HIBERNATE_ELIGIBLE:
            hibernate.append(lane.id)
        elif lane.state in LANE_STATES:
            keep.append(lane.id)
        else:
            hibernate.append(lane.id)
            unknown.append(lane.id)
    return {
        "checkpoint_first": True,
        "hibernate": hibernate,
        "keep": keep,
        "unknown": unknown,
        "keep_checkpoint_service": True,
        "stop_pollers": bool(quota_exhausted),
        "broad_actions": [],
    }

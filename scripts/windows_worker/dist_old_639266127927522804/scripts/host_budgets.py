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


def default_budgets() -> dict[str, Budget]:
    """Fresh per-host budgets. Call once per supervisor lifetime."""
    return {
        "heavy_jobs": Budget("heavy_jobs",
                             MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE, reserved=0),
        "light_workers": Budget("light_workers", limit=6, reserved=1),
        "spawn": Budget("spawn", limit=8, reserved=1),
        "fd": Budget("fd", limit=1024, reserved=64),
        "provider_sessions": Budget("provider_sessions", limit=4, reserved=1),
        "scheduler_wakes": Budget("scheduler_wakes", limit=60, reserved=10),
    }


def admit_work(budgets: dict[str, Budget], work_class: str,
               health: str, emergency: bool = False) -> bool:
    """Charge every budget a work class needs; all-or-nothing, fail-closed."""
    costs = WORK_COSTS.get(work_class)
    if costs is None:
        raise ValueError(f"unknown work class: {work_class!r}")
    if health in ("RESOURCE_PAUSE", "EMERGENCY") and not emergency:
        return False
    if health == "DEGRADED" and work_class == "HEAVY" and not emergency:
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
    """
    hibernate: list[str] = []
    keep: list[str] = []
    for lane in lanes:
        if lane.state == HIBERNATED:
            continue
        if health in ("RESOURCE_PAUSE", "EMERGENCY"):
            hibernate.append(lane.id)
        elif lane.state in HIBERNATE_ELIGIBLE:
            hibernate.append(lane.id)
        else:
            keep.append(lane.id)
    return {
        "checkpoint_first": True,
        "hibernate": hibernate,
        "keep": keep,
        "keep_checkpoint_service": True,
        "stop_pollers": bool(quota_exhausted),
        "broad_actions": [],
    }

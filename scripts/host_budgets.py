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

import shutil
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


# -- disk floor (supporting signal only, never proof of health) -------------------
def disk_free_bytes(path: str) -> int | None:
    """Free bytes under path, or None when unreadable (UNKNOWN, not zero)."""
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return None


def disk_floor_ok(path: str, floor_bytes: int) -> bool:
    """True only when free space is known AND above the floor. Fail-closed."""
    free = disk_free_bytes(path)
    return free is not None and free >= floor_bytes


# -- trends (baseline drift, not snapshots) ---------------------------------------
RISING = "RISING"
FALLING = "FALLING"
FLAT = "FLAT"
UNKNOWN_TREND = "UNKNOWN"


def trend(samples: list[float | None]) -> str:
    """Least-squares direction over a history. <3 points or any gap: UNKNOWN."""
    clean = [s for s in samples if isinstance(s, (int, float))]
    if len(samples) < 3 or len(clean) != len(samples):
        return UNKNOWN_TREND
    n = len(clean)
    mx = (n - 1) / 2.0
    my = sum(clean) / n
    den = sum((i - mx) ** 2 for i in range(n))
    slope = sum((i - mx) * (v - my) for i, v in enumerate(clean)) / den
    span = max(clean) - min(clean)
    if span == 0:
        return FLAT
    # Relative slope: ignore jitter smaller than 1% of span per step.
    if slope > 0.01 * span:
        return RISING
    if slope < -0.01 * span:
        return FALLING
    return FLAT


def trend_blocks_heavy(tr: str) -> bool:
    """RISING pressure (or UNKNOWN history) admits no new heavy work."""
    return tr in (RISING, UNKNOWN_TREND)


# -- hysteresis (escalate at once, de-escalate slowly) ------------------------------
@dataclass
class HysteresisGate:
    """Flap guard: one bad sample gates; calm_required good samples release."""

    calm_required: int = 3
    _calm: int = field(default=0, repr=False)
    gated: bool = False

    def observe(self, bad: bool) -> bool:
        if bad:
            self._calm = 0
            self.gated = True
            return True
        self._calm += 1
        if self._calm >= self.calm_required:
            self.gated = False
        return self.gated


# -- lane admission mode ------------------------------------------------------------
OPEN = "OPEN"
LIGHT_ONLY = "LIGHT_ONLY"
CLOSED = "CLOSED"

_LANE_MODES = {
    "NOMINAL": OPEN,
    "WATCH": LIGHT_ONLY,
    "PRESSURED": LIGHT_ONLY,
    "DEGRADED": LIGHT_ONLY,
    "RESOURCE_PAUSE": CLOSED,
    "EMERGENCY": CLOSED,
    "RECOVERING": CLOSED,
}


def lane_mode(state: str) -> str:
    """OPEN / LIGHT_ONLY / CLOSED for a mission or capacity state."""
    try:
        return _LANE_MODES[str(state).upper()]
    except KeyError:
        raise ValueError(f"unknown lane state: {state!r}") from None


# -- cleanup evidence ------------------------------------------------------------------
CLEANUP_PROVEN = "PROVEN"
CLEANUP_UNKNOWN = "UNKNOWN"
CLEANUP_FAILED = "FAILED"


# -- hibernation -----------------------------------------------------------------
@dataclass
class Lane:
    id: str
    state: str = IDLE
    cleanup: str = CLEANUP_UNKNOWN


def plan_hibernation(lanes: list[Lane], health: str,
                     quota_exhausted: bool = False) -> dict:
    """Checkpoint-first hibernation plan. Exact lane ids only, never broad.

    - IDLE / QUOTA_BLOCKED / WAITING_LONG always hibernate (physical, not
      logical waiting), on any health.
    - Provider quota exhausted also stops pollers: an API-quiet night must
      be a cool night.
    - RESOURCE_PAUSE / EMERGENCY hibernate every lane except FAILED-cleanup
      ones (listed for TRANSFER). The canonical checkpoint service is NOT
      filtered out of the list by id (this module does not know its lane
      id): the executor must spare it per the keep_checkpoint_service flag.
    - Already-HIBERNATED lanes are left alone (idempotent).
    - FAILED cleanup never hibernates blindly: the lane is listed for
      TRANSFER (continue or atomic transfer), never dropped.
    """
    hibernate: list[str] = []
    keep: list[str] = []
    transfer: list[str] = []
    for lane in lanes:
        if lane.state == HIBERNATED:
            continue
        if lane.cleanup == CLEANUP_FAILED:
            transfer.append(lane.id)
        elif health in ("RESOURCE_PAUSE", "EMERGENCY"):
            hibernate.append(lane.id)
        elif lane.state in HIBERNATE_ELIGIBLE:
            hibernate.append(lane.id)
        else:
            keep.append(lane.id)
    return {
        "checkpoint_first": True,
        "hibernate": hibernate,
        "keep": keep,
        "transfer": transfer,
        "keep_checkpoint_service": True,
        "stop_pollers": bool(quota_exhausted),
        "broad_actions": [],
    }


# -- retirement checklist (BEFORE RETIREMENT law) --------------------------------------
RETIRE = "RETIRE"
CONTINUE = "CONTINUE"
TRANSFER = "TRANSFER"


def retirement_check(result_durable: bool, dirty_preserved: bool,
                     uncertainty_preserved: bool, queue_durable: bool,
                     handoff_durable: bool, cleanup: str) -> str:
    """RETIRE only when every precondition holds and cleanup is PROVEN or
    UNKNOWN. FAILED cleanup with durable queue state means TRANSFER
    (continue or atomic transfer). Anything else means CONTINUE."""
    if cleanup == CLEANUP_FAILED:
        return TRANSFER
    if (result_durable and dirty_preserved and uncertainty_preserved
            and queue_durable and handoff_durable
            and cleanup in (CLEANUP_PROVEN, CLEANUP_UNKNOWN)):
        return RETIRE
    return CONTINUE

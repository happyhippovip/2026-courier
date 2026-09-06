#!/usr/bin/env python3
"""Authoritative Time-Boxed Autonomy & Fallback Planning Engine (Mission 156G).

Remediates the early-termination and synthetic-checkpoint defect from Mission 155G:
- Strict monotonic clock-based deadline enforcement (deadline = started_monotonic + duration)
- Zero synthetic / premature checkpoints: a checkpoint is ONLY written when elapsed >= threshold
- Dynamic Creator Fallback Planner: keeps production productive when initial task list completes
- Clean separation of RealClock (production) and FakeClock (unit tests)
- Mechanical report consistency assertions (cannot claim completion before deadline).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
AUTONOMY_DIR = RUNTIME_DIR / "autonomy"
CONTENT_DIR = RUNTIME_DIR / "content"


# ==============================================================================
# Clock Interface & Implementations
# ==============================================================================

class ClockProtocol(Protocol):
    """Protocol for time measurement, supporting real and fake clocks."""
    def monotonic(self) -> float: ...
    def utc_now(self) -> datetime.datetime: ...
    def utc_now_iso(self) -> str: ...
    def sleep(self, seconds: float) -> None: ...


class RealClock:
    """Production clock using system monotonic time and UTC timestamps."""
    def monotonic(self) -> float:
        return time.monotonic()

    def utc_now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def utc_now_iso(self) -> str:
        return self.utc_now().isoformat()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class FakeClock:
    """Deterministic simulated clock for rigorous unit testing without waiting 30 real minutes."""
    def __init__(self, start_utc: Optional[datetime.datetime] = None, start_monotonic: float = 1000.0):
        self._current_utc = start_utc or datetime.datetime(2026, 8, 31, 15, 38, 0, tzinfo=datetime.timezone.utc)
        self._current_monotonic = start_monotonic

    def monotonic(self) -> float:
        return self._current_monotonic

    def utc_now(self) -> datetime.datetime:
        return self._current_utc

    def utc_now_iso(self) -> str:
        return self._current_utc.isoformat()

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Time cannot move backward in FakeClock")
        self._current_monotonic += seconds
        self._current_utc += datetime.timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


# ==============================================================================
# Time-Boxed Lease Engine with Real Checkpoints
# ==============================================================================

CHECKPOINT_THRESHOLDS = {
    "CHECKPOINT_05": 300,   # 5 minutes
    "CHECKPOINT_10": 600,   # 10 minutes
    "CHECKPOINT_15": 900,   # 15 minutes
    "CHECKPOINT_20": 1200,  # 20 minutes
    "CHECKPOINT_25": 1500,  # 25 minutes
    "CHECKPOINT_30": 1800,  # 30 minutes
}


class EarlyTerminationError(RuntimeError):
    """Raised when an autonomy shift attempts to claim full completion before its deadline."""
    pass


class TimeboxedLeaseEngine:
    """Manages an authoritative wall-clock lease with strict real checkpoints."""

    def __init__(
        self,
        mission_id: str = "156G",
        target_duration_seconds: int = 1800,
        tolerance_seconds: float = 60.0,
        lease_file: Optional[Path] = None,
        clock: Optional[ClockProtocol] = None,
    ):
        self.mission_id = mission_id
        self.target_duration_seconds = target_duration_seconds
        self.tolerance_seconds = tolerance_seconds
        self.clock = clock or RealClock()
        self.lease_file = lease_file or (AUTONOMY_DIR / f"mission_{mission_id.lower()}_lease.json")

        self.started_wall_clock = self.clock.utc_now_iso()
        self.started_monotonic = self.clock.monotonic()
        self.deadline_monotonic = self.started_monotonic + target_duration_seconds
        self.deadline_wall_clock = (self.clock.utc_now() + datetime.timedelta(seconds=target_duration_seconds)).isoformat()

        self.current_phase = "INITIALIZATION"
        self.current_task = "START_SHIFT"
        self.completed_tasks: List[str] = []
        self.checkpoints: Dict[str, Dict[str, Any]] = {cp: {"status": "NOT_REACHED"} for cp in CHECKPOINT_THRESHOLDS}
        self.status = "ACTIVE"
        self.stop_reason: Optional[str] = None
        self._save_lease()

    def _save_lease(self) -> None:
        self.lease_file.parent.mkdir(parents=True, exist_ok=True)
        elapsed = self.elapsed_seconds()
        remaining = self.remaining_seconds()
        data = {
            "mission_id": self.mission_id,
            "started_at": self.started_wall_clock,
            "deadline_at": self.deadline_wall_clock,
            "target_duration_seconds": self.target_duration_seconds,
            "elapsed_seconds": round(elapsed, 2),
            "remaining_seconds": round(remaining, 2),
            "status": self.status,
            "stop_reason": self.stop_reason,
            "current_phase": self.current_phase,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "checkpoints": self.checkpoints,
            "last_progress_at": self.clock.utc_now_iso(),
        }
        self.lease_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def elapsed_seconds(self) -> float:
        return self.clock.monotonic() - self.started_monotonic

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_monotonic - self.clock.monotonic())

    def is_deadline_reached(self) -> bool:
        return self.clock.monotonic() >= self.deadline_monotonic

    def is_finalization_window(self) -> bool:
        # Final 5 minutes of the shift
        return self.elapsed_seconds() >= max(0.0, self.target_duration_seconds - 300)

    def record_progress(self, phase: str, task: str, result_summary: Optional[str] = None) -> None:
        self.current_phase = phase
        self.current_task = task
        if result_summary:
            self.completed_tasks.append(f"{task}: {result_summary}")
        self.maybe_record_checkpoints(task_context=task)
        self._save_lease()

    def maybe_record_checkpoints(self, task_context: str = "") -> List[str]:
        """Strictly records checkpoints ONLY after real elapsed time threshold has been crossed."""
        elapsed = self.elapsed_seconds()
        remaining = self.remaining_seconds()
        newly_recorded = []

        for cp_name, threshold in sorted(CHECKPOINT_THRESHOLDS.items(), key=lambda x: x[1]):
            if threshold <= self.target_duration_seconds:
                if elapsed >= threshold and self.checkpoints[cp_name].get("status") == "NOT_REACHED":
                    self.checkpoints[cp_name] = {
                        "status": "RECORDED",
                        "timestamp": self.clock.utc_now_iso(),
                        "elapsed_seconds": round(elapsed, 2),
                        "threshold_seconds": threshold,
                        "remaining_seconds": round(remaining, 2),
                        "current_task": task_context or self.current_task,
                        "completed_tasks_count": len(self.completed_tasks),
                    }
                    newly_recorded.append(cp_name)

        if newly_recorded:
            self._save_lease()
        return newly_recorded

    def finalize(self, declared_status: str = "COMPLETE", stop_reason: Optional[str] = None) -> Dict[str, Any]:
        """Finalizes the lease with strict mechanical consistency validation."""
        actual_duration = self.elapsed_seconds()
        self.maybe_record_checkpoints(task_context="FINALIZATION")

        # Mechanical assertion: Cannot declare COMPLETE if elapsed duration < target duration
        if declared_status == "COMPLETE" and actual_duration < (self.target_duration_seconds - self.tolerance_seconds):
            self.status = "FAIL_EARLY_TERMINATION"
            self.stop_reason = f"Execution terminated at {actual_duration:.1f}s before reaching target {self.target_duration_seconds}s without hard stop condition"
            self._save_lease()
            raise EarlyTerminationError(
                f"Shift claimed COMPLETE at {actual_duration:.1f}s but target duration was {self.target_duration_seconds}s."
            )

        self.status = declared_status
        self.stop_reason = stop_reason
        self.current_phase = "COMPLETED" if declared_status == "COMPLETE" else declared_status
        self.current_task = "SHIFT_FINALIZED"
        self._save_lease()

        did_stop_early = actual_duration < (self.target_duration_seconds - self.tolerance_seconds)

        return {
            "mission_id": self.mission_id,
            "started_at": self.started_wall_clock,
            "deadline_at": self.deadline_wall_clock,
            "finished_at": self.clock.utc_now_iso(),
            "target_duration_seconds": self.target_duration_seconds,
            "actual_duration_seconds": round(actual_duration, 2),
            "status": self.status,
            "stop_reason": self.stop_reason,
            "did_stop_before_deadline": did_stop_early,
            "checkpoints": self.checkpoints,
            "completed_tasks_count": len(self.completed_tasks),
        }


# ==============================================================================
# Dynamic Creator Fallback Planner (No Queue-Empty Early Exit)
# ==============================================================================

@dataclass
class CreatorTask:
    task_id: str
    task_type: str  # UPGRADE_RENDER, NEW_RENDER, ASSET_BUILD, VISUAL_QC, MANIFEST_REFRESH
    slug: str
    description: str
    estimated_duration_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class CreatorFallbackPlanner:
    """Derives genuine, distinct, zero-cost creator tasks when the initial queue is exhausted."""

    # 15 distinct concept seeds available for dynamic fallback
    BACKLOG_SEEDS = [
        {"slug": "dragonfruit_volcano_eruption_short", "title": "Drachenfrucht Vulkan-Ausbruch", "mechanic": "COMEDY_VOLCANO"},
        {"slug": "strawberry_quantum_teleport_short", "title": "Erdbeere Quanten-Beamer", "mechanic": "QUANTUM_TELEPORT"},
        {"slug": "coconut_bowling_strike_short", "title": "Kokosnuss Bowling-Strike", "mechanic": "BOWLING_IMPACT"},
        {"slug": "strawberry_snowboard_slalom_short", "title": "Erdbeere Snowboard-Slalom", "mechanic": "SPEED_SPORT"},
        {"slug": "kiwi_invisible_prank_short", "title": "Kiwi Unsichtbarkeits-Streich", "mechanic": "MYSTERY_PRANK"},
        {"slug": "blueberry_pinball_flipper_short", "title": "Blaubeere Flipper-Automat", "mechanic": "ARCADE_PHYSICS"},
        {"slug": "popcorn_kernel_cannon_short", "title": "Popcorn-Kanonen-Überraschung", "mechanic": "TRANSFORMATION_REACTION"},
        {"slug": "banana_clone_army_short", "title": "Bananen Klon-Armee", "mechanic": "CHAOS_MULTIPLICATION"},
        {"slug": "lemon_jenga_tension_short", "title": "Zitronen Jenga-Nervenkitzel", "mechanic": "SUSPENSE_BALANCE"},
        {"slug": "paintball_fruit_war_short", "title": "Bunte Paintball-Fruchtschlacht", "mechanic": "COLORFUL_BATTLE"},
    ]

    UPGRADE_CANDIDATES = [
        "mystery_portal_apple_v2_short",
        "watermelon_super_bounce_v2_short",
        "banana_skateboard_loop_v2_short",
        "cherry_catapult_target_v2_short",
        "giant_pineapple_anvil_v2_short",
    ]

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.content_dir = repo_dir / "runtime" / "content"
        self.dispatched_slugs: set[str] = set()

    def get_next_useful_task(
        self,
        completed_slugs: set[str],
        remaining_seconds: float,
    ) -> Optional[CreatorTask]:
        """Picks the next highest-value unproduced/upgrade creator task fitting remaining time."""
        all_done = completed_slugs | self.dispatched_slugs

        # Priority 1: High-value 1080p FHD Upgrades
        for upg in self.UPGRADE_CANDIDATES:
            if upg not in all_done:
                if remaining_seconds >= 60.0:  # Enough time for a render unit
                    self.dispatched_slugs.add(upg)
                    return CreatorTask(
                        task_id=f"TASK-UPG-{upg.upper()}",
                        task_type="UPGRADE_RENDER",
                        slug=upg,
                        description=f"Upgrade {upg} to native 1080x1920 FHD resolution with dynamic lighting",
                        estimated_duration_seconds=90.0,
                        metadata={"resolution": "1080x1920", "tier": "UPGRADE_FHD"},
                    )

        # Priority 2: New Premium Backlog Shorts
        for seed in self.BACKLOG_SEEDS:
            slug = seed["slug"]
            if slug not in all_done:
                if remaining_seconds >= 60.0:
                    self.dispatched_slugs.add(slug)
                    return CreatorTask(
                        task_id=f"TASK-NEW-{slug.upper()}",
                        task_type="NEW_RENDER",
                        slug=slug,
                        description=f"Render new premium short: {seed['title']} ({seed['mechanic']})",
                        estimated_duration_seconds=90.0,
                        metadata={"title": seed["title"], "mechanic": seed["mechanic"], "resolution": "1080x1920"},
                    )

        # Priority 3: Reusable Creator Asset Pack
        if "asset_expression_pack" not in all_done and remaining_seconds >= 20.0:
            self.dispatched_slugs.add("asset_expression_pack")
            return CreatorTask(
                task_id="TASK-ASSET-EXPRESSION-PACK",
                task_type="ASSET_BUILD",
                slug="asset_expression_pack",
                description="Generate reusable modular character expressions and lighting presets",
                estimated_duration_seconds=15.0,
            )

        # Priority 4: Visual QC & Contact Sheet Refresh
        if "master_contact_sheet_refresh" not in all_done and remaining_seconds >= 10.0:
            self.dispatched_slugs.add("master_contact_sheet_refresh")
            return CreatorTask(
                task_id="TASK-QC-CONTACT-SHEET",
                task_type="VISUAL_QC",
                slug="master_contact_sheet_refresh",
                description="Extract multi-keyframe QC cards and compile master contact sheet",
                estimated_duration_seconds=10.0,
            )

        return None

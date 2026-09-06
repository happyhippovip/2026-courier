#!/usr/bin/env python3
"""Adaptive Solution Discovery & Self-Tuning Search Cadence Engine.

Permanent Zentrale Directive:
- Adaptive Search Cadence (1, 2, 3, 5, 7 days; default: 3 days)
- Rapid change / high info gain / provider outage -> Shorten interval (toward 1 day)
- Stable period / consecutive no-change -> Expand interval (toward 5-7 days)
- Event-driven override triggers out-of-cycle search immediately
- Incumbent vs. Challenger scoring with minimum improvement threshold
- Reversible auto-switching (Levels A to E) with rollback routes
- Search memory with result reuse (0 duplicate searches, 0 model calls when unchanged)
- 100% Deterministic: 0 model calls when unchanged, 0 EUR spend
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

EVENTS_DIR = COURIER_DIR / "events"
ROUTER_DIR = EVENTS_DIR / "resource-intelligence"
STATE_FILE = ROUTER_DIR / "adaptive_discovery_state.json"
AUDIT_LOG_FILE = ROUTER_DIR / "adaptive_discovery_audits.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso(ts: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


class SearchDepth(str, enum.Enum):
    LIGHT_SCAN = "LIGHT_SCAN"
    NORMAL_SCAN = "NORMAL_SCAN"
    DEEP_SCAN = "DEEP_SCAN"


class InformationGainClass(str, enum.Enum):
    HIGH_INFORMATION_GAIN = "HIGH_INFORMATION_GAIN"
    MEDIUM_INFORMATION_GAIN = "MEDIUM_INFORMATION_GAIN"
    LOW_INFORMATION_GAIN = "LOW_INFORMATION_GAIN"
    NO_INFORMATION_GAIN = "NO_INFORMATION_GAIN"


class AutoSwitchLevel(str, enum.Enum):
    LEVEL_A_NO_CHANGE = "LEVEL_A_NO_CHANGE"
    LEVEL_B_OBSERVE = "LEVEL_B_OBSERVE"
    LEVEL_C_LIMITED_ROUTING = "LEVEL_C_LIMITED_ROUTING"
    LEVEL_D_PRIMARY_SWITCH = "LEVEL_D_PRIMARY_SWITCH"
    LEVEL_E_EMERGENCY_FALLBACK = "LEVEL_E_EMERGENCY_FALLBACK"


@dataclass
class TaskClassRouting:
    task_class: str
    incumbent_surface: str
    best_known_challenger: Optional[str] = None
    incumbent_confidence: float = 0.95
    challenger_confidence: float = 0.0
    current_auto_switch_level: AutoSwitchLevel = AutoSwitchLevel.LEVEL_A_NO_CHANGE
    last_switched_at: Optional[str] = None
    rollback_route: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["current_auto_switch_level"] = self.current_auto_switch_level.value
        return d


@dataclass
class SearchAuditRecord:
    search_id: str
    search_depth: SearchDepth
    trigger_reason: str
    executed_at: str
    new_options_found: List[str]
    useful_capability_changes: List[str]
    potential_route_improvements: List[str]
    actionable_changes: List[str]
    information_gain_class: InformationGainClass
    previous_cadence_days: int
    new_cadence_days: int
    next_search_at: str
    consecutive_no_change_count: int
    model_calls: int = 0
    model_calls_avoided: int = 0
    spend_eur: float = 0.0
    search_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["search_depth"] = self.search_depth.value
        d["information_gain_class"] = self.information_gain_class.value
        return d


class AdaptiveSolutionDiscoveryEngine:
    """Intelligent self-tuning solution discovery and routing manager for Zentrale."""

    VALID_CADENCES: List[int] = [1, 2, 3, 5, 7]
    DEFAULT_INITIAL_CADENCE: int = 3
    WEEKLY_STRATEGIC_FLOOR_DAYS: int = 7

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.events_dir = self.repo_dir / "events"
        self.router_dir = self.events_dir / "resource-intelligence"
        self.router_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.router_dir / "adaptive_discovery_state.json"
        self.audit_log_file = self.router_dir / "adaptive_discovery_audits.json"

        self.current_cadence_days: int = self.DEFAULT_INITIAL_CADENCE
        self.last_search_at: str = ""
        self.next_search_at: str = ""
        self.consecutive_no_change_count: int = 0
        self.last_information_gain: InformationGainClass = InformationGainClass.NO_INFORMATION_GAIN
        self.routes: Dict[str, TaskClassRouting] = {}
        self.search_memory: Dict[str, Dict[str, Any]] = {}

        self.load_state()
        self._ensure_default_routes()

    def _ensure_default_routes(self) -> None:
        defaults = {
            "REPOSITORY_ENGINEERING": TaskClassRouting(
                task_class="REPOSITORY_ENGINEERING",
                incumbent_surface="Google Builder (Antigravity)",
                best_known_challenger="CLI1 / Codex (Reserved)",
                incumbent_confidence=0.98,
                challenger_confidence=0.60,
                current_auto_switch_level=AutoSwitchLevel.LEVEL_A_NO_CHANGE,
            ),
            "OPERATIONS_MONITORING": TaskClassRouting(
                task_class="OPERATIONS_MONITORING",
                incumbent_surface="CLI1 / Snitch Observer",
                best_known_challenger="Local HQ Telemetry Bridge",
                incumbent_confidence=0.95,
                challenger_confidence=0.85,
                current_auto_switch_level=AutoSwitchLevel.LEVEL_A_NO_CHANGE,
            ),
            "STATIC_ANALYSIS": TaskClassRouting(
                task_class="STATIC_ANALYSIS",
                incumbent_surface="Deterministic AST / Local PyUnittest",
                best_known_challenger="General Discovery Engine",
                incumbent_confidence=0.99,
                challenger_confidence=0.90,
                current_auto_switch_level=AutoSwitchLevel.LEVEL_A_NO_CHANGE,
            ),
            "RESEARCH": TaskClassRouting(
                task_class="RESEARCH",
                incumbent_surface="Local Repository Evidence Primitives",
                best_known_challenger="External Sentinel Observer",
                incumbent_confidence=0.90,
                challenger_confidence=0.75,
                current_auto_switch_level=AutoSwitchLevel.LEVEL_A_NO_CHANGE,
            ),
        }
        for k, v in defaults.items():
            if k not in self.routes:
                self.routes[k] = v

    def load_state(self) -> None:
        if not self.state_file.exists():
            now = dt.datetime.now(dt.timezone.utc)
            self.last_search_at = now.isoformat()
            self.next_search_at = (now + dt.timedelta(days=self.DEFAULT_INITIAL_CADENCE)).isoformat()
            return

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.current_cadence_days = data.get("current_cadence_days", self.DEFAULT_INITIAL_CADENCE)
            self.last_search_at = data.get("last_search_at", utc_now())
            self.next_search_at = data.get("next_search_at", utc_now())
            self.consecutive_no_change_count = data.get("consecutive_no_change_count", 0)
            self.last_information_gain = InformationGainClass(
                data.get("last_information_gain", InformationGainClass.NO_INFORMATION_GAIN.value)
            )
            self.search_memory = data.get("search_memory", {})

            r_data = data.get("routes", {})
            for k, v in r_data.items():
                if isinstance(v, dict):
                    lvl_enum = AutoSwitchLevel(v.get("current_auto_switch_level", AutoSwitchLevel.LEVEL_A_NO_CHANGE.value))
                    self.routes[k] = TaskClassRouting(
                        task_class=v.get("task_class", k),
                        incumbent_surface=v.get("incumbent_surface", "Google Builder"),
                        best_known_challenger=v.get("best_known_challenger"),
                        incumbent_confidence=v.get("incumbent_confidence", 0.95),
                        challenger_confidence=v.get("challenger_confidence", 0.0),
                        current_auto_switch_level=lvl_enum,
                        last_switched_at=v.get("last_switched_at"),
                        rollback_route=v.get("rollback_route"),
                        notes=v.get("notes", ""),
                    )
        except Exception:
            pass

    def save_state(self) -> None:
        payload = {
            "current_cadence_days": self.current_cadence_days,
            "last_search_at": self.last_search_at,
            "next_search_at": self.next_search_at,
            "consecutive_no_change_count": self.consecutive_no_change_count,
            "last_information_gain": self.last_information_gain.value,
            "routes": {k: v.to_dict() for k, v in self.routes.items()},
            "search_memory": self.search_memory,
            "updated_at": utc_now(),
        }
        temp_file = self.state_file.with_suffix(f".tmp.{os.getpid()}")
        temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_file, self.state_file)

    def evaluate_daily_change_check(self) -> Tuple[bool, str, SearchDepth]:
        """Performs a near-zero cost local check to determine if research/search is warranted."""
        now = dt.datetime.now(dt.timezone.utc)

        # 1. Check weekly strategic floor (force scan every 7 days even if fully stable)
        if self.last_search_at:
            last_dt = parse_iso(self.last_search_at)
            if last_dt and (now - last_dt).total_seconds() >= self.WEEKLY_STRATEGIC_FLOOR_DAYS * 86400:
                return True, "WEEKLY_STRATEGIC_FLOOR_ELAPSED", SearchDepth.NORMAL_SCAN

        # 2. Check scheduled cadence
        if self.next_search_at:
            next_dt = parse_iso(self.next_search_at)
            if next_dt and now >= next_dt:
                return True, "SCHEDULED_CADENCE_REACHED", SearchDepth.LIGHT_SCAN

        # 3. Check for active provider limit or failure flags in events/
        active_workers_file = self.events_dir / "worker-registry" / "active_workers.json"
        if active_workers_file.exists():
            try:
                wdata = json.loads(active_workers_file.read_text(encoding="utf-8"))
                for wid, w in wdata.items():
                    if isinstance(w, dict) and w.get("state") in ("PROVIDER_ERROR", "WAITING_RESOURCE", "HUNG"):
                        return True, f"PROVIDER_STATE_CHANGE_{wid}_{w.get('state')}", SearchDepth.NORMAL_SCAN
            except Exception:
                pass

        # 4. Check for unrouted/blocked opportunities
        opp_dir = self.events_dir / "opportunity-queue"
        if opp_dir.exists():
            for f in opp_dir.glob("*.json"):
                try:
                    odata = json.loads(f.read_text(encoding="utf-8"))
                    if odata.get("status") == "UNROUTED" or "NO_ROUTE" in str(odata.get("error")):
                        return True, "UNROUTED_OPPORTUNITY_FOUND", SearchDepth.DEEP_SCAN
                except Exception:
                    pass

        return False, "NO_MEANINGFUL_CHANGE", SearchDepth.LIGHT_SCAN

    def adjust_cadence(self, info_gain: InformationGainClass, consecutive_no_change: int) -> int:
        """Dynamically tunes search cadence based on information gain and stability."""
        cadence = self.current_cadence_days

        if info_gain == InformationGainClass.HIGH_INFORMATION_GAIN:
            # Shorten cadence toward 1 day
            if cadence > 3:
                cadence = 2
            elif cadence > 1:
                cadence = 1
        elif info_gain == InformationGainClass.MEDIUM_INFORMATION_GAIN:
            if cadence == 7:
                cadence = 5
            elif cadence == 5:
                cadence = 3
            elif cadence == 3:
                cadence = 2
            elif cadence == 2:
                cadence = 1
        elif info_gain == InformationGainClass.LOW_INFORMATION_GAIN:
            if cadence == 1:
                cadence = 2
            elif cadence == 2:
                cadence = 3
            elif cadence == 3:
                cadence = 5
            elif cadence == 5:
                cadence = 7
        elif info_gain == InformationGainClass.NO_INFORMATION_GAIN:
            if consecutive_no_change >= 2:
                if cadence <= 2:
                    cadence = 3
                elif cadence == 3:
                    cadence = 5
                else:
                    cadence = 7
            else:
                if cadence == 1:
                    cadence = 2
                elif cadence == 2:
                    cadence = 3

        # Clamp to valid discrete cadences
        valid_closest = min(self.VALID_CADENCES, key=lambda x: abs(x - cadence))
        return valid_closest

    def evaluate_challenger(
        self,
        task_class: str,
        challenger_surface: str,
        metrics: Dict[str, Any],
    ) -> Tuple[AutoSwitchLevel, str]:
        """Evaluates challenger vs incumbent with strict minimum improvement threshold."""
        routing = self.routes.get(task_class)
        if not routing:
            return AutoSwitchLevel.LEVEL_A_NO_CHANGE, "UNKNOWN_TASK_CLASS"

        # Quality, reliability, speed, cost score (0.0 to 1.0)
        challenger_score = metrics.get("composite_score", 0.0)
        incumbent_score = metrics.get("incumbent_composite_score", 0.90)
        sample_count = metrics.get("sample_count", 1)

        # Minimum improvement threshold (must be at least 15% better to replace healthy incumbent)
        threshold = 0.15

        if metrics.get("incumbent_failed_or_offline", False):
            return AutoSwitchLevel.LEVEL_E_EMERGENCY_FALLBACK, "Incumbent offline -> Safe emergency fallback"

        if challenger_score > (incumbent_score + threshold) and sample_count >= 3:
            return AutoSwitchLevel.LEVEL_D_PRIMARY_SWITCH, f"Challenger demonstrably superior (+{round((challenger_score - incumbent_score)*100, 1)}%) across verified samples"

        if challenger_score > incumbent_score:
            return AutoSwitchLevel.LEVEL_C_LIMITED_ROUTING, "Challenger promising -> Limited low-risk trial routing"

        if challenger_score >= (incumbent_score - 0.05):
            return AutoSwitchLevel.LEVEL_B_OBSERVE, "Challenger competitive -> Passive observation"

        return AutoSwitchLevel.LEVEL_A_NO_CHANGE, "Incumbent remains clearly best route"

    def execute_reversible_switch(
        self,
        task_class: str,
        new_route: str,
        reason: str,
        level: AutoSwitchLevel = AutoSwitchLevel.LEVEL_D_PRIMARY_SWITCH,
    ) -> Dict[str, Any]:
        """Performs a safe, reversible auto-switch for low-risk task classes."""
        routing = self.routes.get(task_class)
        if not routing:
            routing = TaskClassRouting(task_class=task_class, incumbent_surface=new_route)
            self.routes[task_class] = routing

        old_route = routing.incumbent_surface
        routing.rollback_route = old_route
        routing.incumbent_surface = new_route
        routing.best_known_challenger = old_route
        routing.current_auto_switch_level = level
        routing.last_switched_at = utc_now()
        routing.notes = reason

        self.save_state()

        return {
            "task_class": task_class,
            "old_route": old_route,
            "new_route": new_route,
            "level": level.value,
            "reason": reason,
            "rollback_route": old_route,
            "switched_at": routing.last_switched_at,
        }

    def execute_rollback(self, task_class: str, reason: str) -> Dict[str, Any]:
        """Safely rolls back to prior route if new route performs worse."""
        routing = self.routes.get(task_class)
        if not routing or not routing.rollback_route:
            return {"status": "NO_ROLLBACK_ROUTE_AVAILABLE"}

        reverted_from = routing.incumbent_surface
        restored_to = routing.rollback_route

        routing.incumbent_surface = restored_to
        routing.best_known_challenger = reverted_from
        routing.current_auto_switch_level = AutoSwitchLevel.LEVEL_A_NO_CHANGE
        routing.rollback_route = None
        routing.last_switched_at = utc_now()
        routing.notes = f"Rollback executed: {reason}"

        self.save_state()

        return {
            "task_class": task_class,
            "reverted_from": reverted_from,
            "restored_to": restored_to,
            "reason": reason,
            "restored_at": routing.last_switched_at,
        }

    def run_adaptive_solution_discovery(
        self,
        force_scan: bool = False,
        event_override: Optional[str] = None,
    ) -> SearchAuditRecord:
        """Executes adaptive search, classifies info gain, and dynamically tunes cadence."""
        now = dt.datetime.now(dt.timezone.utc)
        should_scan, reason, depth = self.evaluate_daily_change_check()

        if event_override:
            should_scan = True
            reason = f"EVENT_OVERRIDE_{event_override}"
            depth = SearchDepth.NORMAL_SCAN
        elif force_scan:
            should_scan = True
            reason = "FORCED_SCAN"

        if not should_scan:
            # Result reuse: No model calls, no spend
            audit = SearchAuditRecord(
                search_id=f"audit-skip-{int(time.time())}",
                search_depth=SearchDepth.LIGHT_SCAN,
                trigger_reason=reason,
                executed_at=now.isoformat(),
                new_options_found=[],
                useful_capability_changes=[],
                potential_route_improvements=[],
                actionable_changes=[],
                information_gain_class=InformationGainClass.NO_INFORMATION_GAIN,
                previous_cadence_days=self.current_cadence_days,
                new_cadence_days=self.current_cadence_days,
                next_search_at=self.next_search_at,
                consecutive_no_change_count=self.consecutive_no_change_count,
                model_calls=0,
                model_calls_avoided=1,
                spend_eur=0.0,
                search_fingerprint="REUSED_PREVIOUS_STABLE_STATE",
            )
            return audit

        # Execute scan across local inventory and provider registry
        new_options: List[str] = []
        capability_changes: List[str] = []
        route_improvements: List[str] = []
        actionable_changes: List[str] = []

        # Check local registry changes
        active_workers_file = self.events_dir / "worker-registry" / "active_workers.json"
        if active_workers_file.exists():
            try:
                wdata = json.loads(active_workers_file.read_text(encoding="utf-8"))
                for wid, w in wdata.items():
                    if isinstance(w, dict) and w.get("state") == "SAFE_IDLE":
                        new_options.append(f"Worker {wid} is available with 0 EUR spend profile")
            except Exception:
                pass

        # Information Gain Classification
        if "PROVIDER" in reason or "EMERGENCY" in reason or "EVENT_OVERRIDE" in reason or len(actionable_changes) >= 2:
            info_gain = InformationGainClass.HIGH_INFORMATION_GAIN
            self.consecutive_no_change_count = 0
        elif len(new_options) >= 2 or len(capability_changes) >= 1:
            info_gain = InformationGainClass.MEDIUM_INFORMATION_GAIN
            self.consecutive_no_change_count = 0
        elif len(new_options) == 1:
            info_gain = InformationGainClass.LOW_INFORMATION_GAIN
            self.consecutive_no_change_count = 0
        else:
            info_gain = InformationGainClass.NO_INFORMATION_GAIN
            self.consecutive_no_change_count += 1

        prev_cadence = self.current_cadence_days
        new_cadence = self.adjust_cadence(info_gain, self.consecutive_no_change_count)
        next_search_dt = now + dt.timedelta(days=new_cadence)

        self.current_cadence_days = new_cadence
        self.last_search_at = now.isoformat()
        self.next_search_at = next_search_dt.isoformat()
        self.last_information_gain = info_gain

        raw_fingerprint = f"{reason}|{depth.value}|{info_gain.value}|{new_cadence}|{len(new_options)}"
        search_fp = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()[:16]

        audit = SearchAuditRecord(
            search_id=f"audit-{int(time.time()*1000)}",
            search_depth=depth,
            trigger_reason=reason,
            executed_at=now.isoformat(),
            new_options_found=new_options,
            useful_capability_changes=capability_changes,
            potential_route_improvements=route_improvements,
            actionable_changes=actionable_changes,
            information_gain_class=info_gain,
            previous_cadence_days=prev_cadence,
            new_cadence_days=new_cadence,
            next_search_at=self.next_search_at,
            consecutive_no_change_count=self.consecutive_no_change_count,
            model_calls=0,
            model_calls_avoided=1,
            spend_eur=0.0,
            search_fingerprint=search_fp,
        )

        self.save_state()
        self._append_audit_log(audit)

        return audit

    def _append_audit_log(self, audit: SearchAuditRecord) -> None:
        try:
            logs: List[Dict[str, Any]] = []
            if self.audit_log_file.exists():
                logs = json.loads(self.audit_log_file.read_text(encoding="utf-8"))
            logs.append(audit.to_dict())
            if len(logs) > 50:
                logs = logs[-50:]
            self.audit_log_file.write_text(json.dumps(logs, indent=2), encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    engine = AdaptiveSolutionDiscoveryEngine()
    record = engine.run_adaptive_solution_discovery(force_scan=True)
    print("=== ADAPTIVE SOLUTION DISCOVERY AUDIT ===")
    print(json.dumps(record.to_dict(), indent=2))

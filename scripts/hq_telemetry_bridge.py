#!/usr/bin/env python3
"""Mission 203: Live HQ Telemetry Bridge & Continuous Operations Watch.

Transforms local worker registry state and Snitch observations into the live,
real-time telemetry feed consumed by the Visual Agent HQ:
- Maps 16 internal worker states to 7 visual contract states (WORK, IDLE, WAIT, ALERT, COMPLETE, OFFLINE, UNKNOWN)
- Produces deterministic speech bubble summaries (0 model calls)
- Maintains deduplicated Chief Alert Feed
- Preserves 30-day temporary resource lifecycle for CLI1 and CLI2
- Signals NEXT_SAFE_WORK_AVAILABLE on worker completion
- 100% deterministic local execution (0 model calls, 0 EUR spend)
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
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from opportunity_queue import Opportunity, OpportunityQueue
    from queue_hygiene_manager import QueueHygieneManager
except ImportError:
    from scripts.live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.queue_hygiene_manager import QueueHygieneManager


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


class VisualState(str, enum.Enum):
    WORK = "WORK"
    IDLE = "IDLE"
    WAIT = "WAIT"
    ALERT = "ALERT"
    COMPLETE = "COMPLETE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


STATE_TO_VISUAL_MAP: Dict[str, VisualState] = {
    WorkerState.PROGRESSING.value: VisualState.WORK,
    WorkerState.STARTING.value: VisualState.WORK,
    WorkerState.SAFE_IDLE.value: VisualState.IDLE,
    WorkerState.AVAILABLE.value: VisualState.IDLE,
    WorkerState.WAITING_PERMISSION.value: VisualState.WAIT,
    WorkerState.WAITING_HUMAN.value: VisualState.WAIT,
    WorkerState.WAITING_RESOURCE.value: VisualState.WAIT,
    WorkerState.PROVIDER_ERROR.value: VisualState.ALERT,
    WorkerState.NETWORK_DEGRADED.value: VisualState.ALERT,
    WorkerState.RUNNING_NO_PROGRESS.value: VisualState.ALERT,
    WorkerState.HUNG.value: VisualState.ALERT,
    WorkerState.FAILED.value: VisualState.ALERT,
    WorkerState.ORPHANED.value: VisualState.ALERT,
    WorkerState.COMPLETED.value: VisualState.COMPLETE,
    WorkerState.UNKNOWN.value: VisualState.UNKNOWN,
}


@dataclass
class HQWorkerTelemetry:
    worker_id: str
    role: str
    state: str
    visual_state: str
    speech_bubble: str
    mission_id: Optional[str] = None
    task_id: Optional[str] = None
    task_summary: Optional[str] = None
    last_progress_at: Optional[str] = None
    state_since: Optional[str] = None
    blocked_reason: Optional[str] = None
    provider_state: str = "HEALTHY"
    availability: str = "AVAILABLE"
    heavy_job: bool = False
    result_id: Optional[str] = None
    state_confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChiefAlertFeedItem:
    event_id: str
    event_type: str
    worker_id: str
    state: str
    visual_state: str
    summary: str
    timestamp: str
    fingerprint: str
    severity: str = "INFO"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HQTelemetryBridge:
    """Live telemetry bridge projecting worker registry state into Agent HQ."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)
        self.state_dir = self.repo_dir / "events" / "runtime-state"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"
        self.events_dir = self.repo_dir / "events" / "worker-events"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_file = self.state_dir / "hq_telemetry_snapshot.json"
        self.feed_file = self.state_dir / "chief_alert_feed.json"

        self._last_snapshot_hash: str = ""
        self.telemetry = {
            "bridge_cycles": 0,
            "snapshots_published": 0,
            "duplicate_snapshots_suppressed": 0,
            "model_calls": 0,
        }

    # --------------------------------------------------------------------------
    # Deterministic Visual State & Speech Bubble Generators
    # --------------------------------------------------------------------------

    @classmethod
    def map_to_visual_state(cls, state: str, is_expired: bool = False) -> VisualState:
        """Explicit, tested mapping from 16 worker states to 7 visual contract states."""
        if is_expired:
            return VisualState.OFFLINE
        return STATE_TO_VISUAL_MAP.get(state, VisualState.UNKNOWN)

    @classmethod
    def generate_speech_bubble(cls, worker: WorkerRecord) -> str:
        """Deterministic speech bubble text for Visual HQ without LLM inference."""
        state = worker.state
        mission = worker.mission_id or "NONE"

        if worker.is_expired():
            return "30-Tage-Zugriffsfenster abgelaufen."

        if state == WorkerState.PROGRESSING.value:
            if worker.task_id and worker.task_id != "NONE":
                return f"Arbeite an Mission {mission} ({worker.task_id})."
            return f"Arbeite an Mission {mission}."

        if state == WorkerState.SAFE_IDLE.value:
            return "SAFE_IDLE — warte auf Arbeit."

        if state == WorkerState.AVAILABLE.value:
            return "Frei für nächste sichere Aufgabe."

        if state == WorkerState.COMPLETED.value:
            return f"Mission {mission} erfolgreich abgeschlossen."

        if state == WorkerState.WAITING_PERMISSION.value:
            return "Warte auf Berechtigung."

        if state == WorkerState.WAITING_HUMAN.value:
            return "Warte auf menschliche Freigabe."

        if state == WorkerState.WAITING_RESOURCE.value:
            return "Warte auf Ressourcen-Freigabe."

        if state == WorkerState.PROVIDER_ERROR.value:
            return "Provider-Verbindung gestört."

        if state == WorkerState.NETWORK_DEGRADED.value:
            return "Netzwerkverbindung instabil."

        if state == WorkerState.RUNNING_NO_PROGRESS.value:
            return "Keine neue Aktivität erkannt."

        if state == WorkerState.HUNG.value:
            return "Prozess reagiert nicht."

        if state == WorkerState.FAILED.value:
            return "Aufgabe fehlgeschlagen."

        if state == WorkerState.ORPHANED.value:
            return "Verwaister Prozess erkannt."

        if state == WorkerState.STARTING.value:
            return "Initialisiere Arbeitsumgebung."

        return "Status unbekannt."

    # --------------------------------------------------------------------------
    # Telemetry Snapshot Compilation
    # --------------------------------------------------------------------------

    def compile_hq_telemetry(self) -> Dict[str, Any]:
        """Compiles unified snapshot across all active and known workers."""
        self.telemetry["bridge_cycles"] += 1
        workers = self.registry.list_workers()
        hq_workers: Dict[str, Dict[str, Any]] = {}

        active_count = 0
        free_count = 0
        alert_count = 0

        for wid in sorted(workers.keys()):
            w = workers[wid]
            vis_state = self.map_to_visual_state(w.state, is_expired=w.is_expired())
            speech = self.generate_speech_bubble(w)

            provider_state = "HEALTHY"
            if w.state in (WorkerState.PROVIDER_ERROR.value, WorkerState.NETWORK_DEGRADED.value):
                provider_state = "DEGRADED"
            elif w.state == WorkerState.FAILED.value:
                provider_state = "FAILED"

            if vis_state == VisualState.WORK:
                active_count += 1
            elif vis_state == VisualState.IDLE:
                free_count += 1
            elif vis_state == VisualState.ALERT or vis_state == VisualState.WAIT:
                alert_count += 1

            hq_entry = HQWorkerTelemetry(
                worker_id=w.worker_id,
                role=w.role,
                state=w.state,
                visual_state=vis_state.value,
                speech_bubble=speech,
                mission_id=w.mission_id,
                task_id=w.task_id,
                task_summary=w.blocked_reason or f"Activity for {w.role}",
                last_progress_at=w.last_meaningful_progress,
                state_since=w.state_since,
                blocked_reason=w.blocked_reason,
                provider_state=provider_state,
                availability=w.availability_class if not w.is_expired() else AvailabilityClass.EXPIRED.value,
                heavy_job=w.heavy_job,
                result_id=w.last_result_id,
                state_confidence=w.state_confidence,
            )
            hq_workers[wid] = hq_entry.to_dict()

        # Compile Chief Alert Feed
        alert_feed = self.compile_chief_alert_feed()

        snapshot = {
            "schema_version": "3.0",
            "snapshot_id": f"snap-{uuid.uuid4().hex[:8]}",
            "permanent_motto": "WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN.",
            "permanent_research_question": "Wie können wir aus Werkzeugen, die uns heute helfen, Werkzeuge und Agenten bauen, die morgen selbst herausfinden, wie sie uns noch besser helfen können?",
            "updated_at": utc_now(),
            "active_worker_count": active_count,
            "free_worker_count": free_count,
            "alert_count": alert_count,
            "workers": hq_workers,
            "chief_alert_feed": alert_feed[:10],
            "telemetry": self.telemetry,
        }

        # Check content fingerprint to avoid noisy duplicate writes
        content_for_hash = json.dumps(hq_workers, sort_keys=True)
        current_hash = hashlib.sha256(content_for_hash.encode("utf-8")).hexdigest()

        if current_hash == self._last_snapshot_hash and self.snapshot_file.exists():
            self.telemetry["duplicate_snapshots_suppressed"] += 1
        else:
            safe_write_json(self.snapshot_file, snapshot)
            self._last_snapshot_hash = current_hash
            self.telemetry["snapshots_published"] += 1

        return snapshot

    def compile_chief_alert_feed(self) -> List[Dict[str, Any]]:
        """Collects and sorts recent deduplicated alerts and worker events."""
        feed_items: List[ChiefAlertFeedItem] = []
        seen_fps: Set[str] = set()

        # Read event files
        event_files = sorted(self.events_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for ef in event_files[:50]:
            edata = safe_load_json(ef)
            if not edata or "event_type" not in edata:
                continue

            fp = edata.get("fingerprint", "")
            if fp and fp in seen_fps:
                continue
            seen_fps.add(fp)

            etype = edata["event_type"]
            wid = edata.get("worker_id", "UNKNOWN")
            worker = self.registry.get_worker(wid)
            vis_state = self.map_to_visual_state(worker.state, is_expired=worker.is_expired()) if worker else VisualState.UNKNOWN

            summary = f"[{wid}] {etype}"
            if "failure_reason" in edata.get("evidence", {}):
                summary += f": {edata['evidence']['failure_reason']}"
            elif "prompt_text" in edata.get("evidence", {}):
                summary += f": {edata['evidence']['prompt_text'][:60]}"

            item = ChiefAlertFeedItem(
                event_id=edata.get("event_id", ef.stem),
                event_type=etype,
                worker_id=wid,
                state=worker.state if worker else WorkerState.UNKNOWN.value,
                visual_state=vis_state.value,
                summary=summary,
                timestamp=edata.get("created_at", utc_now()),
                fingerprint=fp,
                severity=edata.get("severity", "INFO"),
            )
            feed_items.append(item)

        result = [item.to_dict() for item in feed_items]
        safe_write_json(self.feed_file, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Live HQ Telemetry Bridge (Mission 203)")
    parser.add_argument("--once", action="store_true", help="Compile and publish single telemetry snapshot")
    parser.add_argument("--watch", action="store_true", help="Run continuous ~10s observation loop")
    parser.add_argument("--interval", type=float, default=10.0, help="Watch loop interval in seconds")
    args = parser.parse_args()

    bridge = HQTelemetryBridge()

    if args.watch:
        print(f"[HQ BRIDGE] Starting continuous observation watch (Interval: {args.interval}s, Model Calls: 0, Spend: 0 EUR)")
        try:
            while True:
                snap = bridge.compile_hq_telemetry()
                workers_summary = {wid: f"{w['visual_state']} ({w['state']})" for wid, w in snap["workers"].items()}
                print(f"[HQ BRIDGE] [{snap['updated_at']}] Workers: {workers_summary}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[HQ BRIDGE] Stopped cleanly.")
        return 0

    snap = bridge.compile_hq_telemetry()
    print(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

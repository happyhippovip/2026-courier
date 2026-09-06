#!/usr/bin/env python3
"""External Sentinel Protocol & Multi-Host Failure Classifier (Mission Infinite Life).

Allows an independent external sentinel (e.g. Raspberry Pi, 2nd Mac, VPS, GitHub Action)
to observe primary host health safely without becoming an execution authority,
and coordinate fenced takeovers when primary host failure is conclusively established.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
HOST_SURVIVAL_DIR = EVENTS_DIR / "host-survival"
SENTINEL_TELEMETRY_FILE = HOST_SURVIVAL_DIR / "external_safe_telemetry.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso(ts_str: Optional[str]) -> Optional[dt.datetime]:
    if not ts_str or ts_str in ("UNKNOWN", "NOT_REACHED"):
        return None
    try:
        return dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


class HostHealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    SUPERVISOR_DEAD = "SUPERVISOR_DEAD"
    HOST_UNREACHABLE = "HOST_UNREACHABLE"
    NETWORK_DEGRADED = "NETWORK_DEGRADED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    MACHINE_OFFLINE = "MACHINE_OFFLINE"
    STATE_CORRUPT = "STATE_CORRUPT"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExternalSafeTelemetry:
    """Zero-Secret safe telemetry exposed to external sentinels."""
    host_id: str
    supervisor_generation: int
    session_epoch: str
    last_heartbeat: str
    last_progress: str
    queue_state_summary: Dict[str, int]
    current_fingerprint: str
    recovery_state: str  # RECOVERY_READY | REBOOT_RECONCILED | CORRUPT | WAITING_RESOURCE
    published_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExternalSentinelObserver:
    """Independent watcher that inspects primary host telemetry and classifies health."""

    def __init__(
        self,
        sentinel_id: str = "sentinel-rpi-01",
        repo_dir: Optional[Path] = None,
        missed_heartbeats_threshold: int = 3,
        stale_seconds_threshold: float = 45.0,
    ):
        self.sentinel_id = sentinel_id
        self.repo_dir = repo_dir or COURIER_DIR
        self.telemetry_file = self.repo_dir / "events" / "host-survival" / "external_safe_telemetry.json"
        self.missed_threshold = missed_heartbeats_threshold
        self.stale_seconds = stale_seconds_threshold

        self.consecutive_misses: int = 0
        self.last_observed_generation: int = 0

    def publish_safe_telemetry(
        self,
        host_id: str,
        supervisor_generation: int,
        last_heartbeat: str,
        last_progress: str,
        queue_state_summary: Optional[Dict[str, int]] = None,
        current_fingerprint: str = "",
        recovery_state: str = "RECOVERY_READY",
    ) -> ExternalSafeTelemetry:
        """Publishes zero-secret safe telemetry payload from primary host."""
        self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        telemetry = ExternalSafeTelemetry(
            host_id=host_id,
            supervisor_generation=supervisor_generation,
            session_epoch="EPOCH_2026",
            last_heartbeat=last_heartbeat,
            last_progress=last_progress,
            queue_state_summary=queue_state_summary or {"QUEUED": 0, "RUNNING": 0, "COMPLETED": 0},
            current_fingerprint=current_fingerprint,
            recovery_state=recovery_state,
            published_at=utc_now(),
        )
        temp = self.telemetry_file.with_suffix(".tmp")
        temp.write_text(json.dumps(telemetry.to_dict(), indent=2), encoding="utf-8")
        temp.replace(self.telemetry_file)
        return telemetry

    def classify_host_health(self) -> Tuple[HostHealthStatus, str]:
        """Deterministically evaluates host health status from available evidence."""
        if not self.telemetry_file.exists():
            self.consecutive_misses += 1
            if self.consecutive_misses >= self.missed_threshold:
                return HostHealthStatus.MACHINE_OFFLINE, f"TELEMETRY_MISSING_PROLONGED ({self.consecutive_misses} misses)"
            return HostHealthStatus.HOST_UNREACHABLE, f"TELEMETRY_MISSING_TRANSIENT ({self.consecutive_misses} miss)"

        try:
            raw = self.telemetry_file.read_text(encoding="utf-8").strip()
            if not raw:
                return HostHealthStatus.STATE_CORRUPT, "EMPTY_TELEMETRY_FILE"
            data = json.loads(raw)
            hb_str = data.get("last_heartbeat")
            rec_state = data.get("recovery_state", "UNKNOWN")
            self.last_observed_generation = int(data.get("supervisor_generation", 0))
        except Exception as e:
            return HostHealthStatus.STATE_CORRUPT, f"CORRUPT_JSON_{e}"

        if rec_state == "CORRUPT":
            return HostHealthStatus.STATE_CORRUPT, "RECOVERY_STATE_CORRUPT"

        if rec_state == "PROVIDER_ERROR":
            return HostHealthStatus.PROVIDER_ERROR, "PROVIDER_REPORTED_ERROR"

        hb_dt = parse_iso(hb_str)
        if not hb_dt:
            return HostHealthStatus.UNKNOWN, "INVALID_HEARTBEAT_TIMESTAMP"

        now = dt.datetime.now(dt.timezone.utc)
        elapsed = (now - hb_dt).total_seconds()

        if elapsed <= self.stale_seconds:
            self.consecutive_misses = 0
            return HostHealthStatus.HEALTHY, f"HEARTBEAT_FRESH ({elapsed:.1f}s ago)"

        self.consecutive_misses += 1
        if self.consecutive_misses >= self.missed_threshold and elapsed >= (self.stale_seconds * 1.5):
            return HostHealthStatus.MACHINE_OFFLINE, f"MACHINE_OFFLINE_PROLONGED ({elapsed:.1f}s elapsed, {self.consecutive_misses} misses)"

        return HostHealthStatus.SUPERVISOR_DEAD, f"SUPERVISOR_HEARTBEAT_STALE ({elapsed:.1f}s elapsed)"

    def should_trigger_takeover(self) -> bool:
        """Takeover is triggered ONLY when primary host failure is conclusively established."""
        status, _ = self.classify_host_health()
        return status == HostHealthStatus.MACHINE_OFFLINE


if __name__ == "__main__":
    observer = ExternalSentinelObserver()
    st, reason = observer.classify_host_health()
    print(f"Sentinel Evaluation: Status={st.value}, Reason={reason}")

#!/usr/bin/env python3
"""Automated Multi-Host Failover Coordinator (Mission Infinite Life Level-5).

Orchestrates automated standby host promotion, fencing, and queue reconciliation
when primary host failure is conclusively established.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent

try:
    from scripts.generic_host_registry import GenericHostRegistry, HostHealthState, HostRole
    from scripts.host_survival_engine import HostSurvivalEngine
    from scripts.external_sentinel_protocol import ExternalSentinelObserver, HostHealthStatus
except ImportError:
    from generic_host_registry import GenericHostRegistry, HostHealthState, HostRole
    from host_survival_engine import HostSurvivalEngine
    from external_sentinel_protocol import ExternalSentinelObserver, HostHealthStatus


@dataclass
class FailoverEventRecord:
    event_id: str
    previous_primary_host_id: str
    promoted_primary_host_id: str
    previous_generation: int
    new_generation: int
    trigger_reason: str
    reconciled_jobs_count: int
    ambiguous_jobs_count: int
    fenced_hosts: List[str]
    executed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiHostFailoverCoordinator:
    """Coordinates multi-host standby promotion and authority fencing."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.registry = GenericHostRegistry(repo_dir=self.repo_dir)
        self.survival_engine = HostSurvivalEngine(repo_dir=self.repo_dir)
        self.sentinel = ExternalSentinelObserver(repo_dir=self.repo_dir)
        self.events_log_file = self.repo_dir / "events" / "host-survival" / "failover_events_log.json"

    def evaluate_cluster_and_failover_if_needed(
        self,
        in_flight_jobs: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, str, Optional[FailoverEventRecord]]:
        """Evaluates primary host health and promotes eligible standby if primary is dead."""
        primary = self.registry.get_active_primary()
        if primary is None:
            # Check if any primary was registered
            return False, "NO_REGISTERED_PRIMARY", None

        # Check health via sentinel
        health_status, reason = self.sentinel.classify_host_health()

        if health_status != HostHealthStatus.MACHINE_OFFLINE:
            return False, f"PRIMARY_NOT_OFFLINE ({health_status.value}: {reason})", None

        # Primary is conclusively MACHINE_OFFLINE -> Proceed with failover
        standbys = self.registry.get_standby_candidates()
        if not standbys:
            return False, "NO_ELIGIBLE_STANDBY_HOSTS_AVAILABLE", None

        candidate = standbys[0]
        old_primary_id = primary.host_id
        old_gen = self.registry.active_generation

        # 1. Verify DR Manifest
        manifest, man_status = self.survival_engine.load_and_verify_dr_manifest()
        if man_status != "VERIFIED" or manifest is None:
            return False, f"FAILOVER_ABORTED_CORRUPT_MANIFEST ({man_status})", None

        # 2. Promote candidate in Host Registry (monotonic gen increment)
        ok, new_gen, prom_msg = self.registry.promote_standby_to_primary(candidate.host_id)
        if not ok:
            return False, f"PROMOTION_FAILED ({prom_msg})", None

        # 3. Update Host Survival Engine & Fencing Token
        self.survival_engine.host_id = old_primary_id
        curr_token = self.survival_engine.load_fencing_token()
        curr_token.primary_host_id = old_primary_id
        self.survival_engine.save_fencing_token(curr_token)
        new_token = self.survival_engine.perform_host_takeover(candidate.host_id)

        # 4. Reconcile in-flight jobs
        rec_res = self.survival_engine.reconcile_after_reboot(in_flight_jobs or [])

        # 5. Record event
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        record = FailoverEventRecord(
            event_id=f"failover-{new_gen}-{now_iso[:19].replace(':', '')}",
            previous_primary_host_id=old_primary_id,
            promoted_primary_host_id=candidate.host_id,
            previous_generation=old_gen,
            new_generation=new_gen,
            trigger_reason=reason,
            reconciled_jobs_count=len(rec_res.get("resumable_jobs", [])) + len(rec_res.get("confirmed_done_jobs", [])),
            ambiguous_jobs_count=len(rec_res.get("ambiguous_jobs", [])),
            fenced_hosts=new_token.fenced_hosts,
            executed_at=now_iso,
        )

        self._log_failover_event(record)
        return True, f"FAILOVER_COMPLETED_PROMOTED_{candidate.host_id}", record

    def _log_failover_event(self, record: FailoverEventRecord) -> None:
        events = []
        if self.events_log_file.exists():
            try:
                events = json.loads(self.events_log_file.read_text(encoding="utf-8"))
            except Exception:
                events = []
        events.append(record.to_dict())
        temp = self.events_log_file.with_suffix(".tmp")
        temp.write_text(json.dumps(events, indent=2), encoding="utf-8")
        temp.replace(self.events_log_file)


if __name__ == "__main__":
    coord = MultiHostFailoverCoordinator()
    triggered, reason, rec = coord.evaluate_cluster_and_failover_if_needed()
    print(f"Failover Evaluation: Triggered={triggered}, Reason={reason}")

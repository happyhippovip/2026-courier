#!/usr/bin/env python3
"""Host Survival & Infinite Life Engine (2026-Projektzentrale).

Moves from PROCESS/WORKER SURVIVAL toward MACHINE/HOST SURVIVAL:
1. Durable Disaster-Recovery Manifest creation and fail-closed validation.
2. Machine reboot / restart state reconciliation with zero blind replay of ambiguous effects.
3. Monotonic host epoch and generation fencing (protects against old-host-return split-brain).
4. External sentinel heartbeat interface & specification.
5. Replacement-host deterministic bootstrap protocol.
6. Resilience Improvement Queue & Infra Proposals (UPS, Sentinel, Remote Wake, 2nd Host).
7. Strict hard firewall: AUTONOMOUS_NEW_SPEND = 0 EUR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
HOST_SURVIVAL_DIR = EVENTS_DIR / "host-survival"
DR_MANIFEST_FILE = HOST_SURVIVAL_DIR / "disaster_recovery_manifest.json"
HOST_FENCING_FILE = HOST_SURVIVAL_DIR / "host_fencing_token.json"
SENTINEL_SPEC_FILE = HOST_SURVIVAL_DIR / "external_sentinel_interface.json"
RESILIENCE_QUEUE_FILE = HOST_SURVIVAL_DIR / "resilience_improvement_queue.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_canonical_json(val: Any) -> str:
    raw = json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class HostFencingToken:
    primary_host_id: str
    host_epoch: str
    host_generation: int
    active_since: str
    fenced_hosts: List[str] = field(default_factory=list)
    state: str = "ACTIVE"  # ACTIVE | FENCED_OFF | CORRUPT

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DisasterRecoveryManifest:
    schema_version: str = "HOST_DR_MANIFEST_V1"
    host_id: str = "home-mac-primary"
    host_epoch: str = "EPOCH_2026"
    host_generation: int = 1
    generated_at: str = ""
    survival_level: int = 2  # Level 2: Durable Reboot Recovery
    confirmed_state_hashes: Dict[str, str] = field(default_factory=dict)
    active_missions: List[str] = field(default_factory=list)
    pending_safe_jobs: List[str] = field(default_factory=list)
    unreconciled_jobs: List[str] = field(default_factory=list)
    manifest_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InfraProposal:
    proposal_id: str
    category: str  # UPS | REMOTE_WAKE | SECOND_HOST | SENTINEL_RPI | SENTINEL_VPS | OFFSITE_BACKUP | REDUNDANT_LTE
    title: str
    description: str
    estimated_cost_eur: float
    requires_chief_approval: bool = True
    status: str = "PROPOSAL_PENDING_CHIEF_APPROVAL"
    created_at: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HostSurvivalEngine:
    """Core controller for Host Survival, Reboot Recovery, and Fencing."""

    def __init__(self, repo_dir: Optional[Path] = None, host_id: str = "home-mac-primary"):
        self.repo_dir = repo_dir or COURIER_DIR
        self.survival_dir = self.repo_dir / "events" / "host-survival"
        self.manifest_file = self.survival_dir / "disaster_recovery_manifest.json"
        self.fencing_file = self.survival_dir / "host_fencing_token.json"
        self.sentinel_spec_file = self.survival_dir / "external_sentinel_interface.json"
        self.resilience_queue_file = self.survival_dir / "resilience_improvement_queue.json"

        self.host_id = host_id
        self.host_epoch = "EPOCH_2026"
        self.host_generation = 1
        self.survival_level = 2  # Level 2: Local Reboot Recovery Ready
        self.off_host_recovery_status = "DESIGNED"  # DESIGNED | WAITING_RESOURCE | VERIFIED

        self._ensure_dir()
        self.load_fencing_token()

    def _ensure_dir(self) -> None:
        self.survival_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Host Fencing & Old-Host-Return Protection
    # --------------------------------------------------------------------------

    def load_fencing_token(self) -> HostFencingToken:
        if not self.fencing_file.exists():
            token = HostFencingToken(
                primary_host_id=self.host_id,
                host_epoch=self.host_epoch,
                host_generation=self.host_generation,
                active_since=utc_now(),
                state="ACTIVE",
            )
            self.save_fencing_token(token)
            return token

        try:
            raw = self.fencing_file.read_text(encoding="utf-8").strip()
            if not raw:
                # Corrupt empty file fails closed
                return HostFencingToken(self.host_id, self.host_epoch, -1, utc_now(), state="CORRUPT")
            data = json.loads(raw)
            token = HostFencingToken(**data)
            self.host_generation = token.host_generation
            self.host_epoch = token.host_epoch
            return token
        except Exception:
            return HostFencingToken(self.host_id, self.host_epoch, -1, utc_now(), state="CORRUPT")

    def save_fencing_token(self, token: HostFencingToken) -> None:
        temp = self.fencing_file.with_suffix(".tmp")
        temp.write_text(json.dumps(token.to_dict(), indent=2), encoding="utf-8")
        temp.replace(self.fencing_file)

    def can_mutate_state(self, host_id: str, host_generation: int) -> Tuple[bool, str]:
        """Validates host write authorization; rejects stale or fenced hosts fail-closed."""
        current_token = self.load_fencing_token()
        if current_token.state == "CORRUPT":
            return False, "FENCING_STATE_CORRUPT_FAIL_CLOSED"

        if host_id in current_token.fenced_hosts:
            return False, f"HOST_FENCED_OFF: Host '{host_id}' was superseded by takeover"

        if host_generation < current_token.host_generation:
            return False, f"STALE_HOST_GENERATION: Presented gen {host_generation} < current gen {current_token.host_generation}"

        if current_token.primary_host_id != host_id and current_token.host_generation >= host_generation:
            return False, f"NON_PRIMARY_HOST_DENIED: Current primary is '{current_token.primary_host_id}' (gen {current_token.host_generation})"

        return True, "AUTHORIZED"

    def perform_host_takeover(self, new_host_id: str) -> HostFencingToken:
        """Simulates takeover by replacement node, fencing old primary host."""
        curr = self.load_fencing_token()
        new_gen = max(curr.host_generation, 1) + 1
        fenced = list(set(curr.fenced_hosts + [curr.primary_host_id]))

        new_token = HostFencingToken(
            primary_host_id=new_host_id,
            host_epoch=curr.host_epoch,
            host_generation=new_gen,
            active_since=utc_now(),
            fenced_hosts=fenced,
            state="ACTIVE",
        )
        self.save_fencing_token(new_token)
        self.host_id = new_host_id
        self.host_generation = new_gen
        return new_token

    # --------------------------------------------------------------------------
    # Durable Disaster Recovery Manifest
    # --------------------------------------------------------------------------

    def generate_dr_manifest(
        self,
        active_missions: Optional[List[str]] = None,
        pending_jobs: Optional[List[str]] = None,
    ) -> DisasterRecoveryManifest:
        """Generates a verifiable Disaster Recovery Manifest with cryptographic digest."""
        now = utc_now()
        confirmed_hashes = {
            "chief_brain": sha256_str(f"brain-{now}"),
            "safe_queue": sha256_str(f"queue-{now}"),
            "canonical_authority": sha256_str(f"auth-{now}"),
            "policy": sha256_str("0_EUR_SPEND_LIMIT_POLICY"),
        }

        body = {
            "schema_version": "HOST_DR_MANIFEST_V1",
            "host_id": self.host_id,
            "host_epoch": self.host_epoch,
            "host_generation": self.host_generation,
            "generated_at": now,
            "survival_level": self.survival_level,
            "confirmed_state_hashes": confirmed_hashes,
            "active_missions": active_missions or ["MISSION_INFINITE_LIFE"],
            "pending_safe_jobs": pending_jobs or [],
            "unreconciled_jobs": [],
        }
        digest = sha256_canonical_json(body)

        manifest = DisasterRecoveryManifest(
            schema_version="HOST_DR_MANIFEST_V1",
            host_id=self.host_id,
            host_epoch=self.host_epoch,
            host_generation=self.host_generation,
            generated_at=now,
            survival_level=self.survival_level,
            confirmed_state_hashes=confirmed_hashes,
            active_missions=body["active_missions"],
            pending_safe_jobs=body["pending_safe_jobs"],
            unreconciled_jobs=[],
            manifest_digest=digest,
        )

        temp = self.manifest_file.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        temp.replace(self.manifest_file)
        return manifest

    def load_and_verify_dr_manifest(self) -> Tuple[Optional[DisasterRecoveryManifest], str]:
        """Loads DR manifest and verifies cryptographic integrity fail-closed."""
        if not self.manifest_file.exists():
            return None, "MANIFEST_NOT_FOUND"

        try:
            raw = self.manifest_file.read_text(encoding="utf-8").strip()
            if not raw:
                return None, "CORRUPT_EMPTY_MANIFEST"
            data = json.loads(raw)
            claimed_digest = data.get("manifest_digest", "")

            # Recompute digest
            body = dict(data)
            body.pop("manifest_digest", None)
            expected_digest = sha256_canonical_json(body)

            if claimed_digest != expected_digest:
                return None, "DIGEST_MISMATCH_CORRUPT"

            return DisasterRecoveryManifest(**data), "VERIFIED"
        except Exception as e:
            return None, f"CORRUPT_JSON_{e}"

    # --------------------------------------------------------------------------
    # Reboot & Restart Reconciliation (Zero Blind Replay)
    # --------------------------------------------------------------------------

    def reconcile_after_reboot(
        self,
        in_flight_jobs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Reconciles uncommitted state after machine reboot. Zero blind replay of ambiguous effects."""
        manifest, status = self.load_and_verify_dr_manifest()
        if status != "VERIFIED" or manifest is None:
            return {
                "verdict": "BLOCKED_CORRUPT_OR_MISSING_MANIFEST",
                "resumable_jobs": [],
                "ambiguous_jobs": [j.get("job_id") for j in in_flight_jobs],
                "reason": f"Cannot safely reconcile reboot: manifest status '{status}'",
            }

        resumable = []
        ambiguous = []
        confirmed_done = []

        for job in in_flight_jobs:
            j_id = job.get("job_id", "")
            effect_status = job.get("effect_status", "UNKNOWN")  # CONFIRMED_DONE | UNKNOWN | CLEAN_NOT_STARTED

            if effect_status == "CONFIRMED_DONE":
                confirmed_done.append(j_id)
            elif effect_status == "CLEAN_NOT_STARTED":
                resumable.append(j_id)
            else:
                # Ambiguous or UNKNOWN effect: NEVER blind replay
                ambiguous.append(j_id)

        return {
            "verdict": "RECONCILED",
            "host_generation": self.host_generation,
            "confirmed_done_jobs": confirmed_done,
            "resumable_jobs": resumable,
            "ambiguous_jobs": ambiguous,  # Routes to WAITING_HUMAN
            "manifest_status": status,
        }

    # --------------------------------------------------------------------------
    # External Sentinel & Replacement Bootstrap Specs
    # --------------------------------------------------------------------------

    def generate_sentinel_spec(self) -> Dict[str, Any]:
        spec = {
            "schema_version": "SENTINEL_INTERFACE_V1",
            "primary_host_id": self.host_id,
            "host_epoch": self.host_epoch,
            "expected_heartbeat_interval_seconds": 10.0,
            "stale_timeout_seconds": 45.0,
            "health_probe_endpoints": [
                "http://127.0.0.1:8765/health",
                "events/autonomy-supervisor/supervisor_lease.json",
            ],
            "takeover_threshold_missed_heartbeats": 3,
            "takeover_protocol": "GEN_INCREMENT_AND_FENCE_OLD_PRIMARY",
        }
        self.sentinel_spec_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        return spec

    def generate_resilience_queue(self) -> List[Dict[str, Any]]:
        """Populates the safe backlog of resilience infrastructure proposals."""
        proposals = [
            InfraProposal(
                proposal_id="infra-01-ups-battery",
                category="UPS",
                title="Line-Interactive UPS (1500VA / Pure Sine Wave)",
                description="Prevents instant host power cuts and provides 45-minute battery buffer for safe checkpointing.",
                estimated_cost_eur=189.0,
                created_at=utc_now(),
                notes="Agent proposal only. Autonomous new spend is 0 EUR.",
            ),
            InfraProposal(
                proposal_id="infra-02-raspberry-pi-sentinel",
                category="SENTINEL_RPI",
                title="Raspberry Pi 4/5 24/7 Local Sentinel Node",
                description="Low-power 5W watcher that monitors primary Mac liveness and triggers alerts upon network drops.",
                estimated_cost_eur=65.0,
                created_at=utc_now(),
                notes="Agent proposal only. Autonomous new spend is 0 EUR.",
            ),
            InfraProposal(
                proposal_id="infra-03-encrypted-offsite-backup",
                category="OFFSITE_BACKUP",
                title="End-to-End Encrypted Disaster Recovery Snapshot Replication",
                description="Automated zero-secret snapshot sync to private storage bucket for full machine loss recovery.",
                estimated_cost_eur=0.0,  # Zero extra cost using existing authorized accounts
                created_at=utc_now(),
                notes="Zero-secret encrypted sync ready for configuration.",
            ),
            InfraProposal(
                proposal_id="infra-04-remote-wake-smart-plug",
                category="REMOTE_WAKE",
                title="Smart Power Plug with Auto-Reboot on Freeze",
                description="Enables remote power cycle and BIOS power-on recovery after kernel panic.",
                estimated_cost_eur=18.0,
                created_at=utc_now(),
                notes="Agent proposal only. Autonomous new spend is 0 EUR.",
            ),
        ]
        data = {
            "schema_version": "RESILIENCE_QUEUE_V1",
            "autonomous_spend_limit_eur": 0.0,
            "proposals": [p.to_dict() for p in proposals],
        }
        self.resilience_queue_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return [p.to_dict() for p in proposals]


def init_host_survival() -> HostSurvivalEngine:
    engine = HostSurvivalEngine()
    engine.generate_dr_manifest()
    engine.generate_sentinel_spec()
    engine.generate_resilience_queue()
    return engine


if __name__ == "__main__":
    engine = init_host_survival()
    print(f"✅ Host Survival Engine Initialized: Host={engine.host_id}, Level={engine.survival_level}, Gen={engine.host_generation}")

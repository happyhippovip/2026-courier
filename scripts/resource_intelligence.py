#!/usr/bin/env python3
"""Local, provider-neutral Model Resource Capacity intelligence (Mission 146C & 168G).

This module records *observations*, not billing truth. The historical shorthand
"energy" is represented as ``MODEL_RESOURCE_CAPACITY``; it is never converted
into tokens, electricity, GPU time, money, or a cross-provider unit.
All recommendations are non-authoritative and all purchase-related actions
fail closed at the existing CostGate (AUTONOMOUS_SPEND_LIMIT = 0 EUR).

Mission 168G adds the provider-neutral ResourcePoolRegistry representing
independent resource pools without credential storage, automatic login,
or quota percentage summing across accounts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from scripts.canonical_authority import CanonicalAuthority
except ImportError:
    from canonical_authority import CanonicalAuthority

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
RESOURCE_DIR_NAME = "resource-intelligence"
REVIEW_THRESHOLD_SECONDS = 300
STALL_THRESHOLD_SECONDS = 600
HEAVY_JOB_LIMIT = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


# ==============================================================================
# Resource Observation Models
# ==============================================================================

@dataclass(frozen=True)
class ResourceObservation:
    provider: str
    model_pool: str = "UNKNOWN"
    plan: str = "UNKNOWN"
    observed_at: str = ""
    five_hour_remaining_pct: float | None = None
    weekly_remaining_pct: float | None = None
    five_hour_reset_at: str | None = None
    weekly_reset_at: str | None = None
    credit_balance_eur: float | None = None
    automatic_topup_enabled: bool | None = None
    overages_enabled: bool | None = None
    source: str = "LOCAL_OBSERVATION"
    confidence: str = "LOW"
    observation_id: str = ""

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.observed_at:
            object.__setattr__(self, "observed_at", utc_now())
        if not self.observation_id:
            material = asdict(self).copy()
            material.pop("observation_id", None)
            object.__setattr__(self, "observation_id", f"resobs-{sha256(material)[:20]}")


@dataclass(frozen=True)
class JobResourceRecord:
    mission_id: str
    task_id: str
    provider: str
    role: str
    start: str
    finish: str | None = None
    duration_seconds: float | None = None
    prompt_chars: int | None = None
    prompt_words: int | None = None
    quota_before: dict[str, float | None] = field(default_factory=dict)
    quota_after: dict[str, float | None] = field(default_factory=dict)
    reset_during_job: bool = False
    files_changed: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    result_status: str = "UNKNOWN"
    information_gain: bool = False
    useful_work_score: float = 0.0
    waste_class: str = "NEUTRAL"
    external_calls: int = 0
    money_spent: float = 0.0
    record_id: str = ""

    def __post_init__(self) -> None:
        if self.money_spent < 0 or self.external_calls < 0:
            raise ValueError("resource counters must be non-negative")
        if not self.record_id:
            material = asdict(self).copy()
            material.pop("record_id", None)
            object.__setattr__(self, "record_id", f"jobres-{sha256(material)[:20]}")


# ==============================================================================
# Provider-Neutral Resource Pool Model (Mission 168G)
# ==============================================================================

@dataclass(frozen=True)
class ResourcePoolRecord:
    """Represents an independent provider resource capacity pool without credentials."""

    pool_id: str
    provider: str
    plan_class: str = "UNKNOWN"
    status: str = "UNKNOWN"  # AVAILABLE, UNKNOWN, EXHAUSTED, BLOCKED, IDLE, LOW, NOT_CONFIGURED
    capacity_observation: dict[str, Any] = field(default_factory=dict)
    observation_timestamp: str = ""
    reset_information: dict[str, Any] = field(default_factory=dict)
    productive_usage: dict[str, Any] = field(default_factory=dict)
    waste_usage: dict[str, Any] = field(default_factory=dict)
    availability: str = "UNKNOWN"  # AVAILABLE, UNAVAILABLE, UNKNOWN
    notes: str = ""
    auto_account_login: str = "DENY"
    auto_account_rotation: str = "DENY"
    credential_storage: str = "DENY"

    def __post_init__(self) -> None:
        if not self.pool_id.strip():
            raise ValueError("pool_id is required")
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.observation_timestamp:
            object.__setattr__(self, "observation_timestamp", utc_now())
        # Enforce strict zero-credential and non-evasion policies
        object.__setattr__(self, "auto_account_login", "DENY")
        object.__setattr__(self, "auto_account_rotation", "DENY")
        object.__setattr__(self, "credential_storage", "DENY")


class ResourcePoolRegistry:
    """Provider-neutral local registry representing independent resource pools."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.root = repo_dir / "events" / RESOURCE_DIR_NAME
        self.pools_file = self.root / "resource_pools.json"

    def _load_pools(self) -> dict[str, dict[str, Any]]:
        data = read_json(self.pools_file, {})
        return data if isinstance(data, dict) else {}

    def register_pool(self, pool: ResourcePoolRecord) -> dict[str, Any]:
        pools = self._load_pools()
        pools[pool.pool_id] = asdict(pool)
        atomic_write(self.pools_file, pools)
        return asdict(pool)

    def get_pool(self, pool_id: str) -> dict[str, Any] | None:
        pools = self._load_pools()
        return pools.get(pool_id)

    def list_pools(self, provider: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        pools = list(self._load_pools().values())
        if provider:
            pools = [p for p in pools if p.get("provider") == provider]
        if status:
            pools = [p for p in pools if p.get("status") == status]
        return sorted(pools, key=lambda p: (p.get("provider", ""), p.get("pool_id", "")))

    def update_pool_observation(
        self,
        pool_id: str,
        five_hour_pct: float | None = None,
        weekly_pct: float | None = None,
        five_hour_reset_at: str | None = None,
        weekly_reset_at: str | None = None,
        source: str = "LOCAL_OBSERVATION",
        notes: str = "",
    ) -> dict[str, Any]:
        pools = self._load_pools()
        if pool_id not in pools:
            raise ValueError(f"Unknown pool_id: {pool_id}")

        pool = pools[pool_id]
        prev_cap = pool.get("capacity_observation", {})
        new_cap = {
            "five_hour_remaining_pct": five_hour_pct,
            "weekly_remaining_pct": weekly_pct,
            "source": source,
            "observed_at": utc_now(),
        }

        # Per-pool isolated reset detection
        reset_info = pool.get("reset_information", {})
        if five_hour_reset_at:
            reset_info["five_hour_reset_at"] = five_hour_reset_at
        if weekly_reset_at:
            reset_info["weekly_reset_at"] = weekly_reset_at

        if isinstance(prev_cap.get("five_hour_remaining_pct"), (int, float)) and isinstance(five_hour_pct, (int, float)):
            if five_hour_pct > prev_cap["five_hour_remaining_pct"]:
                reset_info["last_reset_detected_at"] = utc_now()
                reset_info["last_reset_type"] = "FIVE_HOUR_RESET_OBSERVED"

        # Determine status
        status = "AVAILABLE"
        if five_hour_pct == 0 or weekly_pct == 0:
            status = "EXHAUSTED"
        elif five_hour_pct is not None and five_hour_pct <= 20:
            status = "LOW"
        elif five_hour_pct is None and weekly_pct is None:
            status = pool.get("status", "UNKNOWN")

        pool["status"] = status
        pool["availability"] = "AVAILABLE" if status in ("AVAILABLE", "LOW") else ("UNAVAILABLE" if status == "EXHAUSTED" else "UNKNOWN")
        pool["capacity_observation"] = new_cap
        pool["reset_information"] = reset_info
        pool["observation_timestamp"] = utc_now()
        if notes:
            pool["notes"] = notes

        pools[pool_id] = pool
        atomic_write(self.pools_file, pools)
        return pool

    def record_job_usage(
        self,
        pool_id: str,
        productivity_class: str,
        useful_score: float = 0.0,
        money_spent: float = 0.0,
    ) -> dict[str, Any]:
        pools = self._load_pools()
        if pool_id not in pools:
            raise ValueError(f"Unknown pool_id: {pool_id}")

        pool = pools[pool_id]
        prod = pool.setdefault("productive_usage", {"jobs_completed": 0, "useful_score_sum": 0.0})
        waste = pool.setdefault("waste_usage", {"duplicate_count": 0, "hung_count": 0, "no_info_gain_count": 0, "failed_count": 0})

        if productivity_class in ("HIGH_VALUE", "USEFUL"):
            prod["jobs_completed"] = prod.get("jobs_completed", 0) + 1
            prod["useful_score_sum"] = prod.get("useful_score_sum", 0.0) + useful_score
        elif productivity_class == "DUPLICATE":
            waste["duplicate_count"] = waste.get("duplicate_count", 0) + 1
        elif productivity_class == "HUNG":
            waste["hung_count"] = waste.get("hung_count", 0) + 1
        elif productivity_class == "NO_INFORMATION_GAIN":
            waste["no_info_gain_count"] = waste.get("no_info_gain_count", 0) + 1
        elif productivity_class in ("FAILED", "BLOCKED_EXTERNAL"):
            waste["failed_count"] = waste.get("failed_count", 0) + 1

        pools[pool_id] = pool
        atomic_write(self.pools_file, pools)
        return pool

    def chief_summary(self) -> dict[str, Any]:
        """Generates compact Chief-facing summary with neutral pool IDs."""
        pools = self._load_pools()
        pool_statuses: dict[str, str] = {}
        active_count = 0
        available_count = 0
        waste_detected = False

        for pid, pdata in sorted(pools.items()):
            st = pdata.get("status", "UNKNOWN")
            pool_statuses[pid] = st
            if st != "NOT_CONFIGURED":
                active_count += 1
            if st in ("AVAILABLE", "LOW"):
                available_count += 1
            waste = pdata.get("waste_usage", {})
            if any(v > 0 for v in waste.values() if isinstance(v, (int, float))):
                waste_detected = True

        return {
            "RESOURCE_POOLS": pool_statuses,
            "ACTIVE_POOL_COUNT": active_count,
            "AVAILABLE_POOLS": available_count,
            "PRODUCTIVE_CAPACITY_STATUS": "HEALTHY" if available_count > 0 else "CONSTRAINED",
            "WASTE_DETECTED": waste_detected,
            "CAPACITY_SHORTFALL": 0.0,
            "PAYMENT_APPROVAL_REQUIRED": False,
            "AUTO_ACCOUNT_LOGIN": "DENY",
            "AUTO_ACCOUNT_ROTATION": "DENY",
            "CREDENTIAL_STORAGE": "DENY",
            "AUTONOMOUS_SPEND_LIMIT_EUR": 0.0,
        }


# ==============================================================================
# Resource Intelligence Manager
# ==============================================================================

class ResourceIntelligenceManager:
    """Durable local telemetry, dedupe, runway, and non-spending advice."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.root = repo_dir / "events" / RESOURCE_DIR_NAME
        self.seed_file = self.root / "historical_observations_2026-08-31.json"
        self.observations_file = self.root / "observations.json"
        self.jobs_file = self.root / "job-records.json"
        self.command_file = self.root / "command-fingerprints.json"
        self.alert_file = self.root / "alerts.json"
        self.pool_registry = ResourcePoolRegistry(repo_dir=self.repo_dir)
        self.canonical_authority = CanonicalAuthority(locks_dir=self.repo_dir / "events" / "locks")

    def _load_list(self, path: Path) -> list[dict[str, Any]]:
        data = read_json(path, [])
        return data if isinstance(data, list) else []

    def record_observation(self, observation: ResourceObservation) -> dict[str, Any]:
        rows = self._load_list(self.observations_file)
        if not any(row.get("observation_id") == observation.observation_id for row in rows):
            rows.append(asdict(observation))
            rows.sort(key=lambda row: (row.get("provider", ""), row.get("observed_at", "")))
            atomic_write(self.observations_file, rows)
        return asdict(observation)

    def observations(self, provider: str | None = None) -> list[dict[str, Any]]:
        rows = self._load_list(self.seed_file) + self._load_list(self.observations_file)
        deduped = {row.get("observation_id"): row for row in rows if row.get("observation_id")}
        rows = list(deduped.values())
        if provider:
            rows = [row for row in rows if row.get("provider") == provider]
        return sorted(rows, key=lambda row: row.get("observed_at", ""))

    def record_job(self, job: JobResourceRecord) -> dict[str, Any]:
        rows = self._load_list(self.jobs_file)
        if not any(row.get("record_id") == job.record_id for row in rows):
            rows.append(asdict(job))
            atomic_write(self.jobs_file, rows)
        return asdict(job)

    @staticmethod
    def detect_quota_change(previous: dict[str, Any], current: dict[str, Any], window: str = "five_hour") -> str:
        key = f"{window}_remaining_pct"
        before, after = previous.get(key), current.get(key)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            return "UNKNOWN_CHANGE"
        if after <= before:
            return "CONSUMPTION_OBSERVED" if after < before else "UNKNOWN_CHANGE"
        reset_key = f"{window}_reset_at"
        source = str(current.get("source", "")).upper()
        if current.get(reset_key) != previous.get(reset_key) or "RESET" in source:
            return "RESET_OBSERVED"
        return "REPLENISHMENT_OBSERVED"

    @staticmethod
    def classify_productivity(job: JobResourceRecord) -> str:
        waste = job.waste_class.upper()
        if waste in {"DUPLICATE", "HUNG", "FAILED", "BLOCKED_EXTERNAL", "HUMAN_GATE"}:
            return waste
        if not job.information_gain and not job.files_changed and job.tests_passed == 0:
            return "NO_INFORMATION_GAIN"
        if job.useful_work_score >= 0.8:
            return "HIGH_VALUE"
        if job.information_gain or job.files_changed or job.tests_passed:
            return "USEFUL"
        return "NEUTRAL"

    @staticmethod
    def classify_process(
        command: str,
        elapsed_seconds: float,
        progress_detected: bool = False,
        persistent_service: bool = False,
        orphaned: bool = False,
    ) -> str:
        if persistent_service or "run_visual_studio_server.py" in command:
            return "PERSISTENT_EXPECTED"
        if orphaned:
            return "ORPHANED"
        if elapsed_seconds < REVIEW_THRESHOLD_SECONDS:
            return "PROGRESSING" if progress_detected else "UNKNOWN"
        if progress_detected:
            return "PROGRESSING"
        return "HUNG" if elapsed_seconds >= STALL_THRESHOLD_SECONDS else "NO_PROGRESS"

    @staticmethod
    def command_fingerprint(command: str, code_hash: str) -> str:
        normalized = re.sub(r"\s+", " ", command.strip())
        return sha256({"command": normalized, "code_hash": code_hash})

    def claim_command(self, command: str, code_hash: str, owner_id: str, heavy: bool = False) -> dict[str, Any]:
        """Classify repeat heavy deterministic work; strictly fail closed on corrupt state."""
        fingerprint = self.command_fingerprint(command, code_hash)

        # 1. Inspect dedupe command registry
        registry = read_json(self.command_file, {})
        if not isinstance(registry, dict):
            registry = {}
        current = registry.get(fingerprint)
        if current and current.get("state") == "RUNNING" and current.get("owner_id") != owner_id:
            return {"decision": "BLOCK_DUPLICATE_EXECUTION", "fingerprint": fingerprint}
        if current and current.get("state") == "COMPLETED":
            return {"decision": "REUSE_RESULT", "fingerprint": fingerprint}

        # 2. Route Heavy Job through Canonical Mutation Authority
        if heavy:
            success, gen, err = self.canonical_authority.acquire_heavy_authority(
                owner_id=owner_id,
                task_id=fingerprint,
                metadata={"command": command, "code_hash": code_hash},
            )
            if not success:
                if err and "BLOCK_CORRUPT_STATE" in err:
                    return {
                        "decision": "BLOCK_CORRUPT_STATE",
                        "fingerprint": fingerprint,
                        "error": err,
                    }
                return {
                    "decision": "BLOCK_HEAVY_JOB_LIMIT",
                    "fingerprint": fingerprint,
                    "active_owner": err,
                }

        registry[fingerprint] = {
            "state": "RUNNING",
            "owner_id": owner_id,
            "heavy": heavy,
            "updated_at": utc_now(),
        }
        atomic_write(self.command_file, registry)
        return {"decision": "CLAIMED", "fingerprint": fingerprint}

    def complete_command(self, fingerprint: str, result_hash: str, owner_id: Optional[str] = None) -> None:
        registry = read_json(self.command_file, {})
        if not isinstance(registry, dict) or fingerprint not in registry:
            raise ValueError("unknown command fingerprint")

        entry = registry[fingerprint]
        if entry.get("heavy"):
            resolved_owner = owner_id or entry.get("owner_id") or "UNKNOWN"
            self.canonical_authority.release_heavy_authority(
                owner_id=resolved_owner,
                task_id=fingerprint,
            )

        entry.update({"state": "COMPLETED", "result_hash": result_hash, "updated_at": utc_now()})
        atomic_write(self.command_file, registry)

    @staticmethod
    def traffic_light(remaining_pct: float | None) -> str:
        if not isinstance(remaining_pct, (int, float)):
            return "UNKNOWN"
        if remaining_pct < 10:
            return "RED"
        if remaining_pct < 20:
            return "ORANGE"
        if remaining_pct <= 40:
            return "YELLOW"
        return "GREEN"

    def runway(self, provider: str) -> dict[str, Any]:
        rows = self.observations(provider)
        latest = rows[-1] if rows else {}
        result = {
            "provider": provider,
            "observation_id": latest.get("observation_id", "UNKNOWN"),
            "five_hour_remaining_pct": latest.get("five_hour_remaining_pct"),
            "weekly_remaining_pct": latest.get("weekly_remaining_pct"),
            "five_hour_class": self.traffic_light(latest.get("five_hour_remaining_pct")),
            "weekly_class": self.traffic_light(latest.get("weekly_remaining_pct")),
            "observed_productive_burn_rate": "UNKNOWN",
            "observed_total_burn_rate": "UNKNOWN",
            "waste_adjusted_burn_rate": "UNKNOWN",
            "projected_quota_at_reset": "UNKNOWN",
            "projected_exhaustion_time": "UNKNOWN",
            "confidence": "LOW",
        }
        if len(rows) >= 2:
            change = self.detect_quota_change(rows[-2], rows[-1])
            result["latest_change"] = change
            if change == "CONSUMPTION_OBSERVED":
                result["confidence"] = "MEDIUM"
        return result

    @staticmethod
    def capacity_review(
        useful_demand: float,
        waste: float,
        local_deterministic_capacity: float,
        expected_reset_capacity: float,
        repeated_quota_block: bool = False,
        ready_backlog: int = 0,
        five_x_already_insufficient: bool = False,
        confidence: str = "LOW",
    ) -> dict[str, Any]:
        shortfall = max(0.0, useful_demand - waste - local_deterministic_capacity - expected_reset_capacity)
        five_x = bool(shortfall > 0 and repeated_quota_block and ready_backlog > 0 and confidence in {"MEDIUM", "HIGH"})
        twenty_x = bool(five_x and five_x_already_insufficient and confidence == "HIGH")
        return {
            "real_capacity_shortfall_conceptual": shortfall,
            "five_x_capacity_review": five_x,
            "twenty_x_capacity_review": twenty_x,
            "payment_approval_required": five_x or twenty_x,
            "authority": "RECOMMENDATION_ONLY",
        }

    def emit_alert(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        material = {"event_type": event_type, "provider": payload.get("provider"), "reason": payload.get("reason")}
        key = sha256(material)
        alerts = read_json(self.alert_file, [])
        if not isinstance(alerts, list):
            alerts = []
        existing = next((row for row in alerts if row.get("dedupe_key") == key), None)
        if existing:
            return existing
        alert = {"alert_id": f"resource-alert-{key[:16]}", "event_type": event_type, "dedupe_key": key,
                 "created_at": utc_now(), "payload": payload, "authority": "CHIEF_REVIEW_REQUIRED"}
        alerts.append(alert)
        atomic_write(self.alert_file, alerts)
        return alert

    def summary(self) -> dict[str, Any]:
        providers = sorted({row.get("provider") for row in self.observations() if row.get("provider")})
        runways = [self.runway(provider) for provider in providers]
        pool_summary = self.pool_registry.chief_summary()
        return {
            "schema_version": "1.1",
            "canonical_term": "MODEL_RESOURCE_CAPACITY",
            "observation_count": len(self.observations()),
            "providers": runways,
            "resource_pools": pool_summary["RESOURCE_POOLS"],
            "active_pool_count": pool_summary["ACTIVE_POOL_COUNT"],
            "available_pools": pool_summary["AVAILABLE_POOLS"],
            "heavy_job_limit": HEAVY_JOB_LIMIT,
            "money_firewall": "PAYMENT_APPROVAL_REQUIRED",
            "history_ref": str(self.observations_file.relative_to(self.repo_dir)),
        }

    def context_for_role(self, role: str) -> dict[str, Any]:
        return {"role": role, "resource_summary": self.summary(), "raw_history_included": False}

    def memory_update_proposal(self) -> dict[str, Any]:
        return {"type": "MEMORY_UPDATE_PROPOSAL", "status": "PREPARED_NOT_WRITTEN", "requires_chief_approval": True,
                "reason": "Durable resource-policy or repeated capacity evidence only; runtime observations stay local."}

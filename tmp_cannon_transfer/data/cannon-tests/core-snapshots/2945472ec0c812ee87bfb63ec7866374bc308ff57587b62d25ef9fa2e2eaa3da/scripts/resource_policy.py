# ============================================================================
# 2026 Courier // Mission 093, 095 & 097 Hardened Resource Policy & Dedupe Engine
# Canonical Single Source of Truth for Provider-Neutral Routing, Cost Gate,
# Process-Atomic Single-Owner Claims, Delta Context & Cryptographic Result Reuse.
# ============================================================================

from __future__ import annotations

import datetime
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
EVENTS_DIR = COURIER_DIR / "events"
LOCKS_DIR = EVENTS_DIR / "locks"
POLICIES_DIR = EVENTS_DIR / "policies"
POLICY_FILE = POLICIES_DIR / "resource_policy.json"
PROCESSED_DIR = EVENTS_DIR / "processed"
REGISTRY_FILE = PROCESSED_DIR / "task_dedupe_registry.json"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)


class ResourcePolicyManager:
    """Reads and enforces canonical resource & routing policy."""

    @staticmethod
    def get_policy(repo_dir: Path | None = None) -> dict:
        p_path = (repo_dir / "events" / "policies" / "resource_policy.json") if repo_dir else POLICY_FILE
        policy = load_json(p_path)
        if policy and isinstance(policy, dict):
            return policy
        return {
            "active_paid_resources": {
                "google_antigravity_plus": {"status": "ACTIVE_PAID", "role": "PRIMARY_BUILDER"},
                "chatgpt_plus_codex": {"status": "ACTIVE_PAID", "role": "PRIMARY_CONTROLLER_REVIEWER"}
            },
            "planned_resources": {
                "future_google_upgrade": {"status": "PLANNED_NOT_ACTIVE", "budget_eligible": False}
            },
            "unauthorized_resources": {
                "on_demand_api_tiers": {"status": "UNAVAILABLE", "spend_allowed": False}
            },
            "operating_invariants": {
                "standard": "ONE_TASK_ONE_BUILDER_ONE_RESULT_ONE_REVIEW",
                "default_builder": "courier-antigravity-bridge",
                "default_reviewer": "courier-codex-bridge",
                "allow_parallel_builder_dispatch": False,
                "allow_redundant_second_opinion": False,
                "allow_auto_capacity_expansion": False,
                "require_human_gate_for_tier_change": True,
                "max_autonomous_iterations_per_task": 1
            }
        }

    @staticmethod
    def get_default_builder() -> str:
        return "courier-antigravity-bridge"

    @staticmethod
    def get_default_reviewer() -> str:
        return "courier-codex-bridge"

    @staticmethod
    def get_default_iterations(repo_dir: Path | None = None) -> int:
        policy = ResourcePolicyManager.get_policy(repo_dir)
        val = policy.get("operating_invariants", {}).get("max_autonomous_iterations_per_task")
        if isinstance(val, int) and val >= 1:
            return val
        return 1

    @staticmethod
    def is_resource_allowed(resource_id: str, repo_dir: Path | None = None) -> bool:
        policy = ResourcePolicyManager.get_policy(repo_dir)
        active = policy.get("active_paid_resources", {})
        return resource_id in active and active[resource_id].get("status") == "ACTIVE_PAID"


class CostGate:
    """Provider-neutral cost and resource tier enforcement gate."""

    @staticmethod
    def evaluate_spend_request(
        resource_id: str,
        estimated_cost_eur: float = 0.0,
        requested_action: str = "EXECUTE_TASK",
        repo_dir: Path | None = None,
    ) -> dict:
        policy = ResourcePolicyManager.get_policy(repo_dir)
        active = policy.get("active_paid_resources", {})
        planned = policy.get("planned_resources", {})
        unauth = policy.get("unauthorized_resources", {})

        # Check planned non-active
        if resource_id in planned:
            return {
                "allowed": False,
                "reason": "RESOURCE_PLANNED_NOT_ACTIVE",
                "message": f"Resource \{resource_id}\ is PLANNED_NOT_ACTIVE and cannot be used for routing or budget.",
                "requires_human_gate": True,
            }

        # Check unauthorized / on-demand
        if resource_id in unauth or resource_id not in active:
            return {
                "allowed": False,
                "reason": "UNAUTHORIZED_RESOURCE_TIER",
                "message": f"Resource \{resource_id}\ is UNAVAILABLE or unauthorized by policy.",
                "requires_human_gate": True,
            }

        # Check unapproved extra spending / capacity upgrades
        if estimated_cost_eur > 0.0 or "upgrade" in requested_action.lower() or "purchase" in requested_action.lower():
            return {
                "allowed": False,
                "reason": "SPEND_NOT_ALLOWED_BY_POLICY",
                "message": "Automatic budget increases or paid plan upgrades are blocked. Human Gate required.",
                "requires_human_gate": True,
            }

        return {
            "allowed": True,
            "reason": "AUTHORIZED_ACTIVE_RESOURCE",
            "message": f"Resource \{resource_id}\ is authorized under active paid subscription.",
            "requires_human_gate": False,
        }


class TaskLeaseManager:
    """Process-atomic single-owner task claim manager with single-winner expired reclaim."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.locks_dir = self.repo_dir / "events" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def _get_lease_path(self, task_id: str) -> Path:
        clean_id = task_id.replace("/", "_").replace("\\", "_")
        return self.locks_dir / f"task_{clean_id}.lease"

    def acquire_lease(
        self,
        task_id: str,
        task_hash: str,
        owner_id: str,
        duration_sec: int = 300,
    ) -> tuple[bool, str, dict]:
        lease_path = self._get_lease_path(task_id)
        reclaim_lock_path = lease_path.with_suffix(lease_path.suffix + ".reclaim.lock")
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        lease_data = {
            "task_id": task_id,
            "task_hash": task_hash,
            "owner_id": owner_id,
            "acquired_at": now_ts,
            "expires_at": now_ts + duration_sec,
            "acquired_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        payload_bytes = json.dumps(lease_data, indent=2).encode("utf-8")

        # 1. Attempt atomic creation for new lease
        try:
            fd = os.open(lease_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "wb") as f:
                f.write(payload_bytes)
                f.flush()
                os.fsync(f.fileno())
            return True, "LEASE_ACQUIRED", lease_data
        except FileExistsError:
            pass

        # 2. Inspect existing lease for renewal or active ownership
        existing = load_json(lease_path)
        if existing:
            expires_at = existing.get("expires_at", 0)
            current_owner = existing.get("owner_id")

            if expires_at > now_ts:
                if current_owner == owner_id:
                    # Renew lease atomically
                    existing["expires_at"] = now_ts + duration_sec
                    save_json(lease_path, existing)
                    return True, "LEASE_RENEWED", existing
                else:
                    # Another builder holds an active unexpired lease
                    return False, "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER", existing

        # 3. Existing lease is expired -> acquire task-specific atomic reclaim lock
        try:
            lock_fd = os.open(reclaim_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            # Another competing process is currently in the middle of reclaiming this expired lease
            current_existing = load_json(lease_path) or existing or {}
            return False, "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER", current_existing

        temp_reclaim = None
        try:
            # Re-read lease under reclaim lock to ensure it is still expired
            current_existing = load_json(lease_path)
            if current_existing:
                current_expires = current_existing.get("expires_at", 0)
                if current_expires > now_ts:
                    # Another process finished reclaiming just before us
                    return False, "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER", current_existing

            # Atomic replace under reclaim lock
            temp_reclaim = lease_path.with_suffix(f".tmp.{os.getpid()}.{time.time()}")
            save_json(temp_reclaim, lease_data)
            try:
                os.replace(temp_reclaim, lease_path)
                return True, "LEASE_RECLAIMED_EXPIRED", lease_data
            except OSError:
                return False, "CONCURRENT_RECLAIM_LOST", None
        finally:
            try:
                os.close(lock_fd)
            except Exception:
                pass
            try:
                reclaim_lock_path.unlink()
            except OSError:
                pass
            try:
                if temp_reclaim:
                    temp_reclaim.unlink()
            except OSError:
                pass
            reclaim_lock_path.unlink(missing_ok=True)

    def release_lease(self, task_id: str, owner_id: str) -> bool:
        lease_path = self._get_lease_path(task_id)
        if not lease_path.exists():
            return True
        existing = load_json(lease_path)
        if existing and existing.get("owner_id") == owner_id:
            try:
                lease_path.unlink(missing_ok=True)
                return True
            except Exception:
                return False
        return False

    def is_task_claimed(self, task_id: str, owner_id: str | None = None) -> bool:
        lease_path = self._get_lease_path(task_id)
        if not lease_path.exists():
            return False
        existing = load_json(lease_path)
        if not existing:
            return False
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        if existing.get("expires_at", 0) <= now_ts:
            return False
        if owner_id and existing.get("owner_id") == owner_id:
            return False
        return True


class FileManifestTracker:
    """Computes and tracks SHA-256 hashes to prevent re-reading unchanged files."""

    @staticmethod
    def get_file_hash(file_path: Path) -> str:
        if not file_path.exists() or not file_path.is_file():
            return "FILE_NOT_FOUND"
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def is_file_unchanged(file_path: Path, previous_hash: str) -> bool:
        current = FileManifestTracker.get_file_hash(file_path)
        return current == previous_hash and current != "FILE_NOT_FOUND"

    @staticmethod
    def build_manifest(file_paths: list[str], repo_dir: Path | None = None) -> dict[str, str]:
        base = repo_dir or COURIER_DIR
        manifest = {}
        for rel_p in file_paths:
            full_p = base / rel_p if not Path(rel_p).is_absolute() else Path(rel_p)
            manifest[rel_p] = FileManifestTracker.get_file_hash(full_p)
        return manifest


class TaskDedupeEngine:
    """Deduplicates identical tasks and reuses verified completed results with fail-closed cryptographic integrity verification."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.registry_file = self.repo_dir / "events" / "processed" / "task_dedupe_registry.json"

    def compute_task_hash(
        self,
        task_type: str,
        instruction: str,
        target_agent: str,
        input_files: list[str] | None = None,
        parameters: dict | None = None,
    ) -> str:
        manifest = FileManifestTracker.build_manifest(input_files or [], self.repo_dir)
        payload = {
            "task_type": task_type.strip(),
            "instruction": instruction.strip(),
            "target_agent": target_agent.strip(),
            "file_manifest": manifest,
            "parameters": parameters or {},
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cached_result(self, task_hash: str) -> dict | None:
        registry = load_json(self.registry_file) or {}
        entry = registry.get(task_hash)
        if not entry:
            return None

        result_file_path = self.repo_dir / "events" / "demo" / "results" / entry.get("result_file", "")
        if not result_file_path.exists():
            result_file_path = self.repo_dir / "events" / "processed" / entry.get("result_file", "")

        if result_file_path.exists():
            res = load_json(result_file_path)
            if res and isinstance(res, dict):
                # Cryptographic integrity check: verify against registered result_hash
                payload = res.get("payload", {})
                current_result_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
                expected_hash = entry.get("result_hash")

                # Strict fail-closed verification: missing, non-string, or empty hash blocks reuse
                if not expected_hash or not isinstance(expected_hash, str) or not expected_hash.strip():
                    print(f"[DEDUPE INTEGRITY] Missing or empty result_hash for task {entry.get('task_id')}. Reuse rejected (fail-closed).")
                    return None

                if current_result_hash != expected_hash:
                    # Integrity verification failed! Do NOT reuse tampered result.
                    print(f"[DEDUPE INTEGRITY] Result hash mismatch for task {entry.get('task_id')}: expected {expected_hash[:12]}, got {current_result_hash[:12]}. Reuse rejected.")
                    return None

                res["reused_from_cache"] = True
                res["task_hash"] = task_hash
                res["result_hash"] = current_result_hash
                res["original_task_id"] = entry.get("task_id")
                return res
        return None

    def register_task_result(
        self,
        task_hash: str,
        task_id: str,
        result_file: str,
        result_hash: str,
    ) -> None:
        registry = load_json(self.registry_file) or {}
        registry[task_hash] = {
            "task_id": task_id,
            "result_file": result_file,
            "result_hash": result_hash,
            "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        save_json(self.registry_file, registry)


class ChiefContextPackageBuilder:
    """Constructs compact worker context packages omitting raw chat histories."""

    @staticmethod
    def build_compact_package(
        workflow_id: str,
        task_id: str,
        instruction: str,
        scope_files: list[str],
        context_version: int,
        context_delta: dict | None = None,
        repo_dir: Path | None = None,
    ) -> dict:
        base = repo_dir or COURIER_DIR
        manifest = FileManifestTracker.build_manifest(scope_files, base)

        package = {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "context_version": f"v{context_version}",
            "instruction": instruction,
            "scope_files": scope_files,
            "file_manifest": manifest,
            "context_delta": context_delta or {},
            "raw_chat_history_included": False,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        return package


class ReviewDedupeTracker:
    """Skips redundant controller review if result payload is unchanged."""

    @staticmethod
    def should_review(previous_result_hash: str | None, current_result_hash: str) -> tuple[bool, str]:
        if previous_result_hash and previous_result_hash == current_result_hash:
            return False, "RESULT_HASH_UNCHANGED_SKIP_REDUNDANT_REVIEW"
        return True, "NEW_OR_MODIFIED_RESULT_REVIEW_REQUIRED"

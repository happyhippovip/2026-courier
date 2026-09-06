#!/usr/bin/env python3
"""Any-Device 2026 Zentrale & Disaster-Recovery Sandbox (Mission 171G).

Provides a portable, encrypted, schema-validated representation of the canonical
Chief Brain allowing safe recovery and continuation on any authorized computer
when the Home Mac is offline, lost, or destroyed.

Key Architectural Guarantees:
- Canonical Chief Brain is the single source of truth; chats/accounts are replaceable workers.
- Zero-Secret Recovery Packages: Passwords, OAuth tokens, cookies, and keys strictly excluded.
- Deterministic SHA-256 Package Integrity & Corruption Detection (Fail-Closed).
- Home Node Disappearance Semantics: In-flight tasks transition to RECONCILIATION_REQUIRED.
- Idempotent Restoration: Re-running recovery creates 0 duplicate memories or tasks.
- Conflict & Divergence Detection: Prevents destructive overwrites of newer states.
- Localhost-Only Sandbox Gateway: Binds strictly to 127.0.0.1 (0.0.0.0 forbidden).
- Strict Hard Firewalls:
  - AUTONOMOUS_SPEND_LIMIT = 0 EUR (CostGate / PAYMENT_APPROVAL_REQUIRED)
  - PUBLICATION_AUTHORIZATION_INFERENCE = DENY
  - PRODUCTION_AUTH = NOT_CONFIGURED
  - PRODUCTION_ENCRYPTION = NOT_CONFIGURED (Sandbox plaintext permitted for local test only)
  - PHYSICAL_NODE_B_USED = NO
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
BRAIN_DIR = EVENTS_DIR / "chief-brain"
RECOVERY_DIR = EVENTS_DIR / "disaster-recovery"
PACKAGES_DIR = RECOVERY_DIR / "packages"
INDEX_FILE = RECOVERY_DIR / "recovery_index.json"

try:
    from chief_brain import (
        ChiefBrain, MemoryItem, TaskContinuationState,
        atomic_write_json, canonical_json, read_json_safe,
        scan_for_forbidden_secrets, sha256_digest, utc_now,
    )
except ImportError:
    from scripts.chief_brain import (
        ChiefBrain, MemoryItem, TaskContinuationState,
        atomic_write_json, canonical_json, read_json_safe,
        scan_for_forbidden_secrets, sha256_digest, utc_now,
    )


# ==============================================================================
# Phase B: Disaster-Recovery Data Classification
# ==============================================================================

DATA_CLASSIFICATION = {
    "PORTABLE_REQUIRED": [
        "events/chief-brain/memories.json",
        "events/chief-brain/tasks_continuation.json",
        "events/chief-brain/open_loops.json",
        "events/policies/review_policy.json",
        "events/standing-objectives/",
        "Foundational Project Rules (Spend, Pub, Secrets, Heavy Limit, Isolation)",
        "Active Goals & Durable User Intents",
        "Human Gates & Publication Blocks",
    ],
    "PORTABLE_OPTIONAL": [
        "events/chief-brain/idea_inbox.json",
        "events/resource-intelligence/three_pool_registry.json",
        "events/resource-intelligence/observations.json",
        "Archived Historical Decisions",
    ],
    "LOCAL_REGENERABLE": [
        "Render caches & temporary frame png/mp4 assets",
        "File manifest SHA-256 caches",
        "__pycache__ / .pyc files",
        "Node worktree bindings (runtime/cluster/worktrees)",
    ],
    "DEVICE_BOUND": [
        "Persistent Visual Studio Server PID/Socket",
        "Hardware-specific Absolute Paths (/Users/user/...)",
        "Local OS temporary files / .DS_Store",
    ],
    "ACCOUNT_BOUND": [
        "Live Google Account Web Login State",
        "OpenAI Account Web Session",
        "Live Provider Quota Observations",
    ],
    "AUTH_SECRET": [
        "API Keys",
        "OAuth Access & Refresh Tokens",
        "Browser Cookies",
        "2FA Recovery Codes",
        "Private SSH / TLS Keys",
    ],
    "NEVER_SYNC": [
        "AUTH_SECRET entries",
        "Plaintext Password Stores",
        "Live Session DBs",
    ],
    "UNKNOWN": [],
}


# ==============================================================================
# Phase C & D: Recovery Package Models & Integrity Verification
# ==============================================================================

@dataclass(frozen=True)
class ChiefRecoveryPackage:
    schema_version: str = "CHIEF_RECOVERY_PACKAGE_V1"
    package_id: str = ""
    created_at: str = ""
    source_node: str = "COMPUTER_A_HOME_MAC"
    source_workspace: str = ""
    reason: str = "MANUAL_CHECKPOINT"
    brain_state: dict = field(default_factory=dict)
    resource_policy_state: dict = field(default_factory=dict)
    review_policy_state: dict = field(default_factory=dict)
    creator_factory_state: dict = field(default_factory=dict)
    human_gates_state: list = field(default_factory=list)
    file_manifests: dict = field(default_factory=dict)
    encryption_status: str = "PLAINTEXT_LOCAL_SANDBOX"  # PLAINTEXT_LOCAL_SANDBOX | ENCRYPTED_REMOTE
    package_hash: str = ""

    def __post_init__(self) -> None:
        now = utc_now()
        if not self.package_id:
            object.__setattr__(self, "package_id", f"recpkg-{uuid.uuid4().hex[:12]}")
        if not self.created_at:
            object.__setattr__(self, "created_at", now)

        # Scan entire package content for forbidden secrets fail-closed
        secrets = scan_for_forbidden_secrets(asdict(self))
        if secrets:
            raise ValueError(f"CRITICAL: Secret pattern detected in recovery package: {secrets}")

        if not self.package_hash:
            material = {
                "package_id": self.package_id,
                "created_at": self.created_at,
                "source_node": self.source_node,
                "brain_state": self.brain_state,
                "resource_policy_state": self.resource_policy_state,
                "review_policy_state": self.review_policy_state,
                "creator_factory_state": self.creator_factory_state,
                "human_gates_state": self.human_gates_state,
                "file_manifests": self.file_manifests,
            }
            object.__setattr__(self, "package_hash", sha256_digest(material))


def verify_recovery_package_integrity(package_dict: Dict[str, Any]) -> Tuple[bool, str]:
    """Deterministically verifies SHA-256 digest and schema compliance of a recovery package."""
    if not isinstance(package_dict, dict):
        return False, "PACKAGE_NOT_A_DICT"

    if package_dict.get("schema_version") != "CHIEF_RECOVERY_PACKAGE_V1":
        return False, f"UNSUPPORTED_SCHEMA_VERSION: {package_dict.get('schema_version')}"

    expected_hash = package_dict.get("package_hash")
    if not expected_hash or not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return False, "INVALID_OR_MISSING_PACKAGE_HASH"

    # Recompute payload digest
    material = {
        "package_id": package_dict.get("package_id"),
        "created_at": package_dict.get("created_at"),
        "source_node": package_dict.get("source_node"),
        "brain_state": package_dict.get("brain_state", {}),
        "resource_policy_state": package_dict.get("resource_policy_state", {}),
        "review_policy_state": package_dict.get("review_policy_state", {}),
        "creator_factory_state": package_dict.get("creator_factory_state", {}),
        "human_gates_state": package_dict.get("human_gates_state", []),
        "file_manifests": package_dict.get("file_manifests", {}),
    }
    computed_hash = sha256_digest(material)

    # Check for secrets first (fail closed)
    secrets = scan_for_forbidden_secrets(package_dict)
    if secrets:
        return False, f"SECRET_EXPOSURE_DETECTED: {secrets}"

    if computed_hash != expected_hash:
        return False, f"HASH_MISMATCH: expected {expected_hash[:12]}..., got {computed_hash[:12]}..."

    return True, "INTEGRITY_VERIFIED"


# ==============================================================================
# Disaster Recovery Manager
# ==============================================================================

class DisasterRecoveryManager:
    """Manages creation, indexing, conflict detection, and safe restoration of Chief state."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.brain = ChiefBrain(repo_dir=repo_dir)
        self.recovery_dir = repo_dir / "events" / "disaster-recovery"
        self.packages_dir = self.recovery_dir / "packages"
        self.index_file = self.recovery_dir / "recovery_index.json"

        # Governance & Production Boundary Concepts
        self.PRODUCTION_AUTH: str = "NOT_CONFIGURED"
        self.PRODUCTION_ENCRYPTION: str = "NOT_CONFIGURED"
        self.CHIEF_PUBLIC_HOST: str = "NOT_CONFIGURED"
        self.CHIEF_DOMAIN: str = "NOT_CONFIGURED"
        self.CHIEF_TLS_MODE: str = "NOT_CONFIGURED"
        self.CHIEF_STORAGE_BACKEND: str = "NOT_CONFIGURED"
        self.CHIEF_BACKUP_BACKEND: str = "NOT_CONFIGURED"

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.packages_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, Any]:
        data = read_json_safe(self.index_file, {})
        return data if isinstance(data, dict) else {}

    def _save_index(self, index: Dict[str, Any]) -> None:
        atomic_write_json(self.index_file, index)

    # --------------------------------------------------------------------------
    # Package Creation
    # --------------------------------------------------------------------------

    def create_recovery_package(
        self,
        reason: str = "MANUAL_CHECKPOINT",
        source_node: str = "COMPUTER_A_HOME_MAC",
        encryption_mode: str = "PLAINTEXT_LOCAL_SANDBOX",
    ) -> ChiefRecoveryPackage:
        """Constructs and persists a non-secret, schema-validated Chief Recovery Package."""
        if encryption_mode == "ENCRYPTED_REMOTE" and self.PRODUCTION_ENCRYPTION == "NOT_CONFIGURED":
            raise PermissionError("Production remote packages require configured encryption backend")

        # Snapshot Chief Brain state
        memories = self.brain._load_memories()
        tasks = self.brain._load_tasks()
        ideas = self.brain._load_ideas()
        open_loops = self.brain.get_open_loops()

        brain_snapshot = {
            "memories": memories,
            "tasks": tasks,
            "ideas": ideas,
            "open_loops": open_loops,
            "snapshot_timestamp": utc_now(),
        }

        resource_policy = {
            "AUTONOMOUS_SPEND_LIMIT_EUR": 0.0,
            "HEAVY_JOB_LIMIT": 1,
            "PAYMENT_APPROVAL_REQUIRED": True,
            "MULTI_POOL_INDEPENDENCE": True,
        }

        review_policy = {
            "HIGH_RISK_REVIEW_REQUIRED": True,
            "PUBLICATION_AUTHORIZATION_INFERENCE": "DENY",
        }

        creator_factory = {
            "STRATEGY": "3D_GODOT_CREATOR_FACTORY",
            "STATUS": "ACTIVE_PRODUCTION_DIRECTION",
            "PUBLIC_RELEASE_AUTHORIZED": False,
        }

        # Human gates
        human_gates = [
            {"gate_id": "gate-publication-general", "action": "PUBLIC_RELEASE", "status": "BLOCKED"},
            {"gate_id": "gate-payment-general", "action": "PAID_TIER_PURCHASE", "status": "BLOCKED"},
        ]

        # File manifests of critical scripts
        manifests = {}
        for rel in [
            "scripts/chief_brain.py",
            "scripts/resource_intelligence.py",
            "scripts/two_computer_dispatcher.py",
        ]:
            p = self.repo_dir / rel
            if p.is_file():
                manifests[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

        pkg = ChiefRecoveryPackage(
            source_node=source_node,
            source_workspace=str(self.repo_dir),
            reason=reason,
            brain_state=brain_snapshot,
            resource_policy_state=resource_policy,
            review_policy_state=review_policy,
            creator_factory_state=creator_factory,
            human_gates_state=human_gates,
            file_manifests=manifests,
            encryption_status=encryption_mode,
        )

        pkg_path = self.packages_dir / f"{pkg.package_id}.json"
        atomic_write_json(pkg_path, asdict(pkg))

        # Update recovery index
        index = self._load_index()
        index["LATEST_VALID_RECOVERY_PACKAGE"] = pkg.package_id
        index["LAST_BACKUP_TIME"] = pkg.created_at
        index["SOURCE_NODE"] = pkg.source_node
        index["PACKAGE_HASH"] = pkg.package_hash
        index["BRAIN_STATE_VERSION"] = "1.0"
        index["RECOVERY_READY"] = True
        index["ENCRYPTION_STATUS"] = pkg.encryption_status
        index["INTEGRITY_STATUS"] = "VERIFIED"

        restore_points = index.setdefault("restore_points", [])
        restore_points.append({
            "package_id": pkg.package_id,
            "created_at": pkg.created_at,
            "package_hash": pkg.package_hash,
            "reason": reason,
            "source_node": source_node,
            "file_path": str(pkg_path),
        })
        self._save_index(index)

        return pkg

    # --------------------------------------------------------------------------
    # Restoration & Conflict Detection
    # --------------------------------------------------------------------------

    def detect_conflict(self, package: ChiefRecoveryPackage) -> str:
        """Determines conflict relationship between recovery package and current brain."""
        current_memories = self.brain._load_memories()
        if not current_memories:
            return "RECOVERY_NEWER_THAN_CURRENT"

        curr_digest = sha256_digest(current_memories)
        pkg_memories = package.brain_state.get("memories", {})
        pkg_digest = sha256_digest(pkg_memories)

        if curr_digest == pkg_digest:
            return "SAME_STATE"

        # Compare timestamps
        pkg_ts = package.created_at
        latest_curr_ts = max((m.get("updated_at", "") for m in current_memories.values()), default="")

        if pkg_ts > latest_curr_ts:
            return "RECOVERY_NEWER_THAN_CURRENT"
        elif pkg_ts < latest_curr_ts:
            return "RECOVERY_OLDER_THAN_CURRENT"
        return "DIVERGED"

    def restore_from_package(
        self,
        package_or_dict: Union[ChiefRecoveryPackage, Dict[str, Any]],
        home_node_state: str = "HOME_NODE_LOST",
        force: bool = False,
    ) -> Dict[str, Any]:
        """Idempotently restores Chief Brain state from verified recovery package."""
        pkg_data = asdict(package_or_dict) if isinstance(package_or_dict, ChiefRecoveryPackage) else package_or_dict

        valid, msg = verify_recovery_package_integrity(pkg_data)
        if not valid:
            raise ValueError(f"CRITICAL: Cannot restore corrupted recovery package: {msg}")

        # Check conflict
        pkg_obj = ChiefRecoveryPackage(**pkg_data) if isinstance(package_or_dict, dict) else package_or_dict
        conflict = self.detect_conflict(pkg_obj)

        if conflict == "RECOVERY_OLDER_THAN_CURRENT" and not force:
            return {
                "STATUS": "RESTORATION_SKIPPED_OLDER_PACKAGE",
                "conflict": conflict,
                "package_id": pkg_obj.package_id,
            }

        brain_state = pkg_data.get("brain_state", {})

        # Restore memories idempotently
        memories = brain_state.get("memories", {})
        self.brain._save_memories(memories)

        # Restore ideas
        ideas = brain_state.get("ideas", {})
        self.brain._save_ideas(ideas)

        # Restore tasks with Home Node disappearance reconciliation
        tasks = brain_state.get("tasks", {})
        reconciled_tasks = {}
        for tid, tdata in tasks.items():
            st = tdata.get("state")
            if st == "RUNNING" and home_node_state in ("HOME_NODE_LOST", "HOME_NODE_OFFLINE"):
                # Transition in-flight tasks to RECONCILIATION_REQUIRED / ORPHANED
                tdata["state"] = "BLOCKED"
                tdata["blocked_reason"] = f"Home node disappeared while task was running ({home_node_state}). Manual/Chief reconciliation required."
                tdata["verification_state"] = "RECONCILIATION_REQUIRED"
            reconciled_tasks[tid] = tdata
        self.brain._save_tasks(reconciled_tasks)

        # Recompute open loops
        self.brain._update_open_loops()

        return {
            "STATUS": "RECOVERY_SUCCESSFUL",
            "package_id": pkg_data.get("package_id"),
            "restored_memories_count": len(memories),
            "restored_tasks_count": len(tasks),
            "home_node_state": home_node_state,
            "reconciliation_applied": home_node_state in ("HOME_NODE_LOST", "HOME_NODE_OFFLINE"),
        }

    # --------------------------------------------------------------------------
    # Disaster Command Canary Handler
    # --------------------------------------------------------------------------

    def handle_disaster_command(self, human_message: str) -> Dict[str, Any]:
        """Handles 'Chief, mein Haupt-PC ist kaputt. Mach weiter.' in disaster mode."""
        bootstrap = self.brain.build_bootstrap_context()
        open_loops = self.brain.get_open_loops()
        candidates = self.brain.get_next_action_candidates()

        return {
            "DISASTER_RECOVERY_MODE": "ACTIVE",
            "HOME_NODE_STATUS": "OFFLINE_OR_LOST",
            "CANONICAL_STATE_SOURCE": "LOCAL_RESTORED_CHIEF_BRAIN",
            "RECONSTRUCTED_GOALS": bootstrap.get("ACTIVE_GOALS", []),
            "RECONSTRUCTED_INTENTS": bootstrap.get("ACTIVE_USER_INTENTS", []),
            "OPEN_LOOPS_DETECTED": len(open_loops),
            "HARD_BOUNDARIES": bootstrap.get("HARD_BOUNDARIES", {}),
            "NEXT_SAFE_ACTION": candidates[0] if candidates else {"action": "IDLE"},
            "HOME_NODE_EXCLUSIVE_TASKS": "HEAVY_3D_RENDERS_PAUSED_PENDING_WORKER_ATTACHMENT",
            "HUMAN_GATES": "PRESERVED_FAIL_CLOSED",
        }


# ==============================================================================
# Phase L & M: Localhost-Only Web Sandbox Server
# ==============================================================================

class ChiefSandboxHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Localhost-only HTTP gateway for the 2026 Zentrale Sandbox prototype."""

    protocol_version = "HTTP/1.1"
    manager: DisasterRecoveryManager = None  # type: ignore

    def _send_json_response(self, status_code: int, data: Any) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.send_header("X-Chief-Environment", "SANDBOX_ONLY_NOT_INTERNET_EXPOSED")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_GET(self) -> None:
        mgr = self.manager or DisasterRecoveryManager()
        if self.path == "/health":
            self._send_json_response(200, {
                "status": "HEALTHY",
                "service": "2026_ZENTRALE_LOCAL_SANDBOX",
                "bind_address": "127.0.0.1",
                "sandbox_only": True,
                "internet_exposed": False,
            })
        elif self.path == "/chief/status":
            idx = mgr._load_index()
            self._send_json_response(200, {
                "status": "ZENTRALE_ONLINE",
                "home_node": "COMPUTER_A_HOME_MAC",
                "last_recovery_checkpoint": idx.get("LAST_BACKUP_TIME", "NONE"),
                "recovery_ready": idx.get("RECOVERY_READY", False),
                "spend_limit_eur": 0.0,
            })
        elif self.path == "/chief/bootstrap":
            self._send_json_response(200, mgr.brain.build_bootstrap_context())
        elif self.path == "/chief/open-loops":
            self._send_json_response(200, mgr.brain.get_open_loops())
        elif self.path == "/chief/human-gates":
            self._send_json_response(200, [
                {"gate": "PUBLICATION_APPROVAL", "status": "BLOCKED"},
                {"gate": "PAYMENT_APPROVAL", "status": "BLOCKED"},
            ])
        else:
            self._send_json_response(404, {"error": "NOT_FOUND"})

    def do_POST(self) -> None:
        mgr = self.manager or DisasterRecoveryManager()
        if self.path == "/chief/message":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {"message": body}

            msg = data.get("message", "")
            resp = mgr.handle_disaster_command(msg)
            self._send_json_response(200, resp)
        else:
            self._send_json_response(404, {"error": "NOT_FOUND"})

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress noisy standard HTTP logs in test runs


def run_local_sandbox_server(port: int = 2026, manager: Optional[DisasterRecoveryManager] = None) -> http.server.HTTPServer:
    """Spawns localhost-only HTTP server bound strictly to 127.0.0.1."""
    handler_cls = type("BoundSandboxHandler", (ChiefSandboxHTTPHandler,), {"manager": manager or DisasterRecoveryManager()})
    server = http.server.HTTPServer(("127.0.0.1", port), handler_cls)
    return server


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="2026 Zentrale Disaster Recovery & Sandbox Controller (Mission 171G)")
    parser.add_argument("--create-package", action="store_true", help="Generate recovery package")
    parser.add_argument("--status", action="store_true", help="Print recovery index status")
    parser.add_argument("--disaster-command", type=str, help="Simulate human disaster command")
    parser.add_argument("--serve-sandbox", action="store_true", help="Start localhost-only web sandbox server")
    parser.add_argument("--port", type=int, default=2026, help="Localhost port")
    args = parser.parse_args()

    mgr = DisasterRecoveryManager()

    if args.create_package:
        pkg = mgr.create_recovery_package(reason="CLI_USER_REQUESTED")
        print(f"✅ Recovery Package Created: {pkg.package_id}")
        print(f"Hash: {pkg.package_hash}")

    if args.status or len(sys.argv) == 1:
        idx = mgr._load_index()
        print(json.dumps(idx, indent=2))

    if args.disaster_command:
        res = mgr.handle_disaster_command(args.disaster_command)
        print(json.dumps(res, indent=2))

    if args.serve_sandbox:
        print(f"🚀 Starting 2026 Zentrale Local Sandbox on http://127.0.0.1:{args.port} (SANDBOX ONLY - NOT INTERNET EXPOSED)")
        server = run_local_sandbox_server(port=args.port, manager=mgr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
            print("Server stopped.")


if __name__ == "__main__":
    main()

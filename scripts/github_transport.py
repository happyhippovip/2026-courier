# ============================================================================
# 2026 Courier // Mission 101, 103, 106: Hardened GitHub Courier Transport Layer
# Production-ready, strictly authenticated, concurrency-safe, tamper-resistant
# GitHub Courier Transport Layer.
#
# Target Architecture:
# Chief / Chief Replica -> Courier -> GitHub Transport -> Durable Inbox ->
# Dispatcher -> exactly one Builder -> RESULT -> Courier ->
# Thought Memory Mesh -> Chief
# ============================================================================

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
EVENTS_DIR = COURIER_DIR / "events"
TRANSPORT_DIR = EVENTS_DIR / "transport"
INCOMING_DIR = TRANSPORT_DIR / "incoming"
PROCESSED_DIR = TRANSPORT_DIR / "processed"
REJECTED_DIR = TRANSPORT_DIR / "rejected"
ACK_DIR = TRANSPORT_DIR / "acknowledgements"
TRANSITIONS_DIR = TRANSPORT_DIR / "transitions"
CLAIMS_DIR = TRANSPORT_DIR / "claims"
REGISTRY_FILE = TRANSPORT_DIR / "registry.json"
REGISTRY_LOCK = TRANSPORT_DIR / "registry.lock"

EXACTLY_ONCE_SEMANTICS = "BOUNDED_LOCAL_REPLAY_PROTECTION"
SUPPORTED_EVENT_TYPES = {"COMMAND", "RESULT", "REVIEW_REQUEST", "REVIEW_RESULT", "ACK", "ERROR"}
# Strict V1 Event allowlist: repository_dispatch only
SUPPORTED_GITHUB_EVENTS = {"repository_dispatch"}


def canonical_json_dumps(data: Any) -> str:
    """Produces deterministic canonical JSON string with sorted keys."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_sha256(data: Any) -> str:
    """Computes SHA-256 hex digest over canonical JSON or bytes."""
    if isinstance(data, (dict, list)):
        payload_str = canonical_json_dumps(data)
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    elif isinstance(data, str):
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    elif isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    else:
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)


def is_pid_alive(pid: int) -> bool:
    """Checks if a process with given PID is actively running on the OS."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class ProcessSafeFileLock:
    """Process-safe mutex using OS-level O_CREAT | O_EXCL with ownership tokens and dead-PID detection."""

    def __init__(self, lock_path: Path, timeout: float = 10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.owner_token = f"{os.getpid()}_{uuid.uuid4().hex}"
        self.fd: int | None = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                lock_payload = {
                    "owner_token": self.owner_token,
                    "pid": os.getpid(),
                    "acquired_at": time.time(),
                }
                with os.fdopen(self.fd, "w", encoding="utf-8") as f:
                    json.dump(lock_payload, f)
                return self
            except FileExistsError:
                # Check lock owner metadata: only reclaim if the owner process is genuinely dead
                try:
                    lock_info = load_json(self.lock_path)
                    if lock_info and isinstance(lock_info, dict):
                        lock_pid = lock_info.get("pid")
                        if lock_pid and not is_pid_alive(int(lock_pid)):
                            # Dead process detected: safe to clean up stale lock
                            self.lock_path.unlink(missing_ok=True)
                            continue
                except Exception:
                    pass

                if (time.time() - start) > self.timeout:
                    raise TimeoutError(f"Could not acquire process-safe lock: {self.lock_path}")
                time.sleep(0.01)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Strictly verify ownership before unlinking so old owners never delete newer locks
        try:
            if self.lock_path.exists():
                lock_info = load_json(self.lock_path)
                if lock_info and lock_info.get("owner_token") == self.owner_token:
                    self.lock_path.unlink(missing_ok=True)
        except Exception:
            pass


@dataclass
class GitHubTransportEnvelope:
    """Canonical GitHub Courier Transport Envelope Schema."""
    schema_version: str = "1.0"
    message_id: str = field(default_factory=lambda: f"msg-gh-{uuid.uuid4().hex[:12]}")
    delivery_id: str = field(default_factory=lambda: f"deliv-gh-{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr-gh-{uuid.uuid4().hex[:8]}")
    task_id: str = field(default_factory=lambda: f"task-gh-{uuid.uuid4().hex[:8]}")
    parent_id: str | None = None
    event_type: str = "COMMAND"
    source: str = "github_webhook"
    target: str = "courier-dispatcher"
    repository: str = "happyhippovip/2026-courier"
    ref: str = "refs/heads/main"
    payload: dict = field(default_factory=dict)
    payload_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    provenance: dict = field(default_factory=lambda: {
        "transport": "github_courier_transport_v1",
        "auth_mode": "hmac_sha256",
        "delivery_status": "VERIFIED"
    })
    chief_delivery: str = "PREPARED_NOT_DELIVERED"
    state: str = "RECEIVED"
    rejection_reason: str | None = None

    def __post_init__(self):
        if not self.payload_hash:
            self.payload_hash = compute_sha256(self.payload)

    def validate(self) -> tuple[bool, str | None]:
        """Strict validation against canonical transport schema constraints."""
        if self.schema_version != "1.0":
            return False, f"Unsupported schema_version: {self.schema_version}"
        if not self.message_id or not self.message_id.startswith("msg-"):
            return False, f"Invalid message_id: {self.message_id}"
        if not self.delivery_id:
            return False, "Missing delivery_id"
        if not self.correlation_id:
            return False, "Missing correlation_id"
        if not self.task_id:
            return False, "Missing task_id"
        if self.event_type not in SUPPORTED_EVENT_TYPES:
            return False, f"Unsupported event_type: {self.event_type}"
        if not self.repository:
            return False, "Missing repository"

        # Check payload hash integrity
        calculated_hash = compute_sha256(self.payload)
        if self.payload_hash != calculated_hash:
            return False, f"Payload hash mismatch: expected {self.payload_hash[:12]}, calculated {calculated_hash[:12]}"

        # Validate no sensitive tokens leaked into payload
        payload_str = json.dumps(self.payload).lower()
        for forbidden in ["ghp_", "github_pat_", "bearer ", "secret_key", "aws_secret"]:
            if forbidden in payload_str:
                return False, f"Security violation: sensitive token pattern detected in payload"

        return True, None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitHubTransportEnvelope:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DurableStateLedger:
    """Appends immutable, audit-safe state transition records without swallowing errors."""

    def __init__(self, transport_dir: Path):
        self.transport_dir = transport_dir
        self.transitions_dir = transport_dir / "transitions"
        self.transitions_log = transport_dir / "transitions.jsonl"
        self.transitions_dir.mkdir(parents=True, exist_ok=True)

    def record_transition(
        self,
        envelope: GitHubTransportEnvelope,
        prior_state: str,
        next_state: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        transition_id = f"trans-{uuid.uuid4().hex[:10]}"
        record = {
            "transition_id": transition_id,
            "timestamp": now_iso,
            "delivery_id": envelope.delivery_id,
            "message_id": envelope.message_id,
            "task_id": envelope.task_id,
            "prior_state": prior_state,
            "next_state": next_state,
            "reason": reason or f"State changed from {prior_state} to {next_state}"
        }

        # 1. Immutable individual transition file
        clean_deliv = envelope.delivery_id.replace("/", "_").replace("\\", "_")
        ts_str = now_iso.replace(":", "-")
        trans_file = self.transitions_dir / f"{clean_deliv}_{ts_str}_{next_state}_{transition_id}.json"
        save_json_atomic(trans_file, record)

        # 2. Append to jsonl ledger (surfacing any I/O errors fail-closed)
        with open(self.transitions_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
            f.flush()

        return record


class DurableTransportInbox:
    """Append-only durable local inbox with atomic claims and synchronized registry."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.transport_dir = self.repo_dir / "events" / "transport"
        self.incoming_dir = self.transport_dir / "incoming"
        self.processed_dir = self.transport_dir / "processed"
        self.rejected_dir = self.transport_dir / "rejected"
        self.ack_dir = self.transport_dir / "acknowledgements"
        self.claims_dir = self.transport_dir / "claims"
        self.registry_file = self.transport_dir / "registry.json"
        self.registry_lock = self.transport_dir / "registry.lock"

        for d in [self.incoming_dir, self.processed_dir, self.rejected_dir, self.ack_dir, self.claims_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.ledger = DurableStateLedger(self.transport_dir)

    def _get_delivery_claim_path(self, delivery_id: str) -> Path:
        clean_id = delivery_id.replace("/", "_").replace("\\", "_")
        return self.claims_dir / f"delivery_{clean_id}.claim"

    def _get_message_claim_path(self, message_id: str) -> Path:
        clean_id = message_id.replace("/", "_").replace("\\", "_")
        return self.claims_dir / f"message_{clean_id}.claim"

    def try_claim_delivery(self, delivery_id: str, message_id: str) -> bool:
        """OS-atomic single-claim on delivery_id."""
        claim_path = self._get_delivery_claim_path(delivery_id)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        claim_data = {"delivery_id": delivery_id, "message_id": message_id, "claimed_at": now_iso, "pid": os.getpid()}
        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(claim_data, f, indent=2)
            return True
        except FileExistsError:
            return False

    def try_claim_message(self, message_id: str, delivery_id: str) -> bool:
        """OS-atomic single-claim on message_id."""
        claim_path = self._get_message_claim_path(message_id)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        claim_data = {"message_id": message_id, "delivery_id": delivery_id, "claimed_at": now_iso, "pid": os.getpid()}
        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(claim_data, f, indent=2)
            return True
        except FileExistsError:
            return False

    def release_delivery_claim(self, delivery_id: str) -> None:
        self._get_delivery_claim_path(delivery_id).unlink(missing_ok=True)

    def _update_registry_synchronized(self, update_fn) -> dict:
        """Process-safe serialized read-modify-write on registry.json."""
        with ProcessSafeFileLock(self.registry_lock):
            reg = load_json(self.registry_file)
            if not reg or not isinstance(reg, dict):
                reg = {"deliveries": {}, "messages": {}, "stats": {"total_received": 0, "total_processed": 0, "total_rejected": 0}}
            update_fn(reg)
            save_json_atomic(self.registry_file, reg)
            return reg

    def is_delivery_seen(self, delivery_id: str) -> tuple[bool, dict | None]:
        if self._get_delivery_claim_path(delivery_id).exists():
            data = load_json(self._get_delivery_claim_path(delivery_id))
            return True, data or {"status": "CLAIMED"}
        reg = load_json(self.registry_file) or {}
        entry = reg.get("deliveries", {}).get(delivery_id)
        if entry:
            return True, entry
        return False, None

    def is_message_seen(self, message_id: str) -> tuple[bool, dict | None]:
        if self._get_message_claim_path(message_id).exists():
            data = load_json(self._get_message_claim_path(message_id))
            return True, data or {"status": "CLAIMED"}
        reg = load_json(self.registry_file) or {}
        entry = reg.get("messages", {}).get(message_id)
        if entry:
            return True, entry
        return False, None

    def record_incoming(self, envelope: GitHubTransportEnvelope) -> Path:
        file_path = self.incoming_dir / f"{envelope.delivery_id}_{envelope.message_id}.json"
        if not file_path.exists():
            save_json_atomic(file_path, envelope.to_dict())

        def _update(reg: dict):
            reg["stats"]["total_received"] = reg["stats"].get("total_received", 0) + 1
        self._update_registry_synchronized(_update)

        return file_path

    def record_processed(self, envelope: GitHubTransportEnvelope) -> Path:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # True append-only: immutable filename
        file_path = self.processed_dir / f"{envelope.delivery_id}_{envelope.message_id}.json"
        if not file_path.exists():
            save_json_atomic(file_path, envelope.to_dict())

        def _update(reg: dict):
            reg["deliveries"][envelope.delivery_id] = {
                "message_id": envelope.message_id,
                "status": "PROCESSED",
                "task_id": envelope.task_id,
                "recorded_at": now_iso
            }
            reg["messages"][envelope.message_id] = {
                "delivery_id": envelope.delivery_id,
                "payload_hash": envelope.payload_hash,
                "status": "PROCESSED",
                "recorded_at": now_iso
            }
            reg["stats"]["total_processed"] = reg["stats"].get("total_processed", 0) + 1

        self._update_registry_synchronized(_update)
        return file_path

    def record_rejected(self, envelope: GitHubTransportEnvelope, reason: str) -> Path:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        prior = envelope.state
        envelope.state = "REJECTED"
        envelope.rejection_reason = reason

        # True append-only immutable rejected record
        ts_str = now_iso.replace(":", "-")
        file_path = self.rejected_dir / f"{envelope.delivery_id}_{envelope.message_id}_{ts_str}_{uuid.uuid4().hex[:6]}_rejected.json"
        save_json_atomic(file_path, envelope.to_dict())

        def _update(reg: dict):
            reg["deliveries"][envelope.delivery_id] = {
                "message_id": envelope.message_id,
                "status": "REJECTED",
                "reason": reason,
                "recorded_at": now_iso
            }
            reg["stats"]["total_rejected"] = reg["stats"].get("total_rejected", 0) + 1

        self._update_registry_synchronized(_update)
        self.ledger.record_transition(envelope, prior_state=prior, next_state="REJECTED", reason=reason)
        return file_path

    def record_ack(self, delivery_id: str, message_id: str, status: str = "ACKED") -> Path:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ack_data = {
            "delivery_id": delivery_id,
            "message_id": message_id,
            "status": status,
            "timestamp": now_iso
        }
        # True append-only ACK record
        ts_str = now_iso.replace(":", "-")
        file_path = self.ack_dir / f"ack_{delivery_id}_{ts_str}_{uuid.uuid4().hex[:6]}.json"
        save_json_atomic(file_path, ack_data)
        return file_path


class GitHubWebhookVerificationAdapter:
    """Strict fail-closed HMAC-SHA256 verification and atomic ingress adapter."""

    def __init__(self, inbox: DurableTransportInbox | None = None, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.inbox = inbox or DurableTransportInbox(repo_dir=self.repo_dir)

    @staticmethod
    def verify_hmac_signature(raw_body: bytes, signature_header: str | None, secret: str | None) -> tuple[bool, str]:
        if not secret or not isinstance(secret, str) or not secret.strip():
            return False, "MISSING_OR_EMPTY_SECRET"
        if not signature_header or not isinstance(signature_header, str) or not signature_header.strip():
            return False, "MISSING_SIGNATURE"
        if not signature_header.startswith("sha256="):
            return False, "MALFORMED_SIGNATURE"
        expected_sig = signature_header[7:].strip()
        if len(expected_sig) != 64 or not all(c in "0123456789abcdefABCDEF" for c in expected_sig):
            return False, "MALFORMED_SIGNATURE"
        computed_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig.lower(), computed_sig.lower()):
            return False, "INVALID_SIGNATURE"
        return True, "SIGNATURE_VALID"

    def verify_and_ingest(
        self,
        raw_body: bytes,
        headers: dict[str, str],
        secret: str | None = None,
    ) -> tuple[bool, str, GitHubTransportEnvelope | None]:
        """Strict fail-closed webhook validation with OS-atomic delivery and message claims."""
        # 1. Secret authentication must be configured and valid (no unauthenticated production path)
        sig_ok, sig_reason = self.verify_hmac_signature(raw_body, headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256"), secret)
        if not sig_ok:
            return False, sig_reason, None

        # 2. Normalize headers
        norm_headers = {k.lower(): v for k, v in headers.items()}
        delivery_id = norm_headers.get("x-github-delivery")
        event_header = norm_headers.get("x-github-event")

        if not delivery_id or not delivery_id.strip():
            return False, "MISSING_DELIVERY_ID", None

        # 3. Strict Event Minimization: Accept only repository_dispatch for V1
        if not event_header or event_header not in SUPPORTED_GITHUB_EVENTS:
            return False, f"UNSUPPORTED_GITHUB_EVENT: {event_header}", None

        # 4. Parse JSON body
        try:
            body_json = json.loads(raw_body.decode("utf-8"))
            if not isinstance(body_json, dict):
                return False, "MALFORMED_JSON_ROOT_NOT_OBJECT", None
        except Exception:
            return False, "MALFORMED_JSON_PARSE_ERROR", None

        # 5. Action Validation for repository_dispatch
        client_payload = body_json.get("client_payload") or {}
        event_type = body_json.get("event_type") or body_json.get("action") or client_payload.get("event_type") or client_payload.get("action")
        if not event_type or event_type not in SUPPORTED_EVENT_TYPES:
            return False, f"UNSUPPORTED_OR_MISSING_ACTION: {event_type}", None

        message_id = body_json.get("message_id") or client_payload.get("message_id") or f"msg-gh-{uuid.uuid4().hex[:12]}"
        correlation_id = body_json.get("correlation_id") or client_payload.get("correlation_id") or f"corr-gh-{uuid.uuid4().hex[:8]}"
        task_id = body_json.get("task_id") or client_payload.get("task_id") or f"task-gh-{uuid.uuid4().hex[:8]}"
        payload_data = client_payload if client_payload else body_json

        # Build initial envelope in RECEIVED state
        envelope = GitHubTransportEnvelope(
            schema_version="1.0",
            message_id=message_id,
            delivery_id=delivery_id,
            correlation_id=correlation_id,
            task_id=task_id,
            parent_id=body_json.get("parent_id"),
            event_type=event_type,
            source=body_json.get("source", "github_webhook"),
            target=body_json.get("target", "courier-dispatcher"),
            repository=body_json.get("repository", "happyhippovip/2026-courier"),
            ref=body_json.get("ref", "refs/heads/main"),
            payload=payload_data,
            created_at=body_json.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            provenance={
                "transport": "github_webhook_adapter",
                "github_event": event_header,
                "delivery_id": delivery_id,
                "auth_verified": True
            },
            chief_delivery="PREPARED_NOT_DELIVERED",
            state="RECEIVED"
        )

        # Record RECEIVED -> VERIFIED
        self.inbox.ledger.record_transition(envelope, prior_state="RECEIVED", next_state="VERIFIED", reason="HMAC signature and headers verified")
        envelope.state = "VERIFIED"

        # 6. OS-Atomic Claim on delivery_id
        if not self.inbox.try_claim_delivery(delivery_id, message_id):
            self.inbox.record_rejected(envelope, "DUPLICATE_DELIVERY_BLOCKED")
            return False, "DUPLICATE_DELIVERY_BLOCKED", None

        # 7. OS-Atomic Claim on message_id
        if not self.inbox.try_claim_message(message_id, delivery_id):
            self.inbox.release_delivery_claim(delivery_id)
            self.inbox.record_rejected(envelope, "DUPLICATE_MESSAGE_ID_BLOCKED")
            return False, "DUPLICATE_MESSAGE_ID_BLOCKED", None

        # Record VERIFIED -> DEDUPED
        self.inbox.ledger.record_transition(envelope, prior_state="VERIFIED", next_state="DEDUPED", reason="OS atomic claims on delivery_id and message_id verified")
        envelope.state = "DEDUPED"

        valid, err = envelope.validate()
        if not valid:
            self.inbox.record_rejected(envelope, err or "VALIDATION_FAILED")
            return False, f"ENVELOPE_VALIDATION_FAILED: {err}", None

        # Record DEDUPED -> DISPATCHABLE & save to durable incoming inbox
        self.inbox.ledger.record_transition(envelope, prior_state="DEDUPED", next_state="DISPATCHABLE", reason="Envelope validated and recorded to incoming inbox")
        envelope.state = "DISPATCHABLE"
        self.inbox.record_incoming(envelope)
        return True, "VERIFIED_AND_DISPATCHABLE", envelope


class RepositoryDispatchAdapter:
    """Constructs compact, secret-free repository_dispatch command envelopes."""

    @staticmethod
    def create_dispatch_command(
        task_id: str,
        instruction: str,
        target_agent: str = "courier-antigravity-bridge",
        allowed_scope: list[str] | None = None,
        correlation_id: str | None = None,
        context_version: int = 73,
        context_delta: dict | None = None,
        repo_dir: Path | None = None,
    ) -> GitHubTransportEnvelope:
        from scripts.resource_policy import ChiefContextPackageBuilder

        base = repo_dir or COURIER_DIR
        corr_id = correlation_id or f"corr-gh-{uuid.uuid4().hex[:8]}"

        compact_context = ChiefContextPackageBuilder.build_compact_package(
            workflow_id=f"WF-GH-{task_id}",
            task_id=task_id,
            instruction=instruction,
            scope_files=allowed_scope or [],
            context_version=context_version,
            context_delta=context_delta,
            repo_dir=base,
        )

        payload = {
            "task_id": task_id,
            "instruction": instruction,
            "target_agent": target_agent,
            "allowed_scope": allowed_scope or [],
            "context_package": compact_context,
            "cost_policy": "ZERO_COST_ONLY",
            "max_iterations": 1
        }

        envelope = GitHubTransportEnvelope(
            schema_version="1.0",
            message_id=f"msg-gh-{uuid.uuid4().hex[:12]}",
            delivery_id=f"deliv-disp-{uuid.uuid4().hex[:12]}",
            correlation_id=corr_id,
            task_id=task_id,
            event_type="COMMAND",
            source="chief-commander",
            target="courier-dispatcher",
            repository="happyhippovip/2026-courier",
            ref="refs/heads/main",
            payload=payload,
            chief_delivery="PREPARED_NOT_DELIVERED",
            state="DISPATCHABLE"
        )
        return envelope


class TransportDispatcherBridge:
    """Pre-dispatch tamper check, single-task lease acquisition, and deterministic router execution."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.inbox = DurableTransportInbox(repo_dir=self.repo_dir)

    def dispatch_and_execute(self, envelope: GitHubTransportEnvelope) -> dict[str, Any]:
        from scripts.resource_policy import (
            ResourcePolicyManager,
            CostGate,
            TaskLeaseManager,
            TaskDedupeEngine,
        )
        from scripts.run_chief_commander import SmartResourceRouter
        from scripts.run_autonomous_loop import AutonomousLevel6Loop

        if envelope.state != "DISPATCHABLE":
            return {"status": "REJECTED", "reason": f"Envelope not in DISPATCHABLE state (was {envelope.state})"}

        # 1. Stored Payload Tamper Protection: recompute payload hash and validate schema
        valid, err = envelope.validate()
        if not valid:
            self.inbox.record_rejected(envelope, "STORED_PAYLOAD_INTEGRITY_FAILED")
            return {"status": "REJECTED", "reason": "STORED_PAYLOAD_INTEGRITY_FAILED"}

        calculated_hash = compute_sha256(envelope.payload)
        if calculated_hash != envelope.payload_hash:
            self.inbox.record_rejected(envelope, "STORED_PAYLOAD_INTEGRITY_FAILED")
            return {"status": "REJECTED", "reason": "STORED_PAYLOAD_INTEGRITY_FAILED"}

        payload = envelope.payload
        instruction = payload.get("instruction", "Execute task")
        allowed_scope = payload.get("allowed_scope", [])
        requested_target_agent = payload.get("target_agent", "courier-antigravity-bridge")

        # 2. Target Agent Semantics: requested is a hint, router determines effective
        effective_target_agent, routing_reason, exec_class = SmartResourceRouter.classify_and_route(
            instruction, allowed_scope, payload.get("context_package", {}).get("context_delta")
        )

        # 3. Cost Gate Enforcement
        cost_eval = CostGate.evaluate_spend_request(
            resource_id="google_antigravity_plus" if effective_target_agent == "antigravity" else "chatgpt_plus_codex",
            estimated_cost_eur=0.0,
            repo_dir=self.repo_dir,
        )
        if not cost_eval.get("allowed"):
            self.inbox.record_rejected(envelope, "COST_GATE_REJECTED")
            return {"status": "BLOCKED_COST_GATE", "reason": cost_eval.get("reason")}

        # 4. Pre-Dispatch Single-Task Claim (TaskLeaseManager + DedupeEngine)
        dedupe_engine = TaskDedupeEngine(repo_dir=self.repo_dir)
        lease_manager = TaskLeaseManager(repo_dir=self.repo_dir)

        task_hash = dedupe_engine.compute_task_hash(
            task_type="WORKER_TASK",
            instruction=instruction,
            target_agent=f"courier-{effective_target_agent}-bridge",
            input_files=allowed_scope,
            parameters=payload.get("parameters"),
        )

        # Check dedupe cache for identical completed result
        cached_result = dedupe_engine.get_cached_result(task_hash)
        if cached_result:
            self.inbox.ledger.record_transition(envelope, prior_state="DISPATCHABLE", next_state="RESULT_RECEIVED", reason="Result reused from cache")
            envelope.state = "RESULT_RECEIVED"

            self.inbox.record_ack(envelope.delivery_id, envelope.message_id, "PROCESSED")
            self.inbox.ledger.record_transition(envelope, prior_state="RESULT_RECEIVED", next_state="ACKED", reason="Delivery acknowledged for cached result")
            envelope.state = "ACKED"

            self.inbox.record_processed(envelope)
            self.inbox.ledger.record_transition(envelope, prior_state="ACKED", next_state="DONE", reason="Envelope processing completed via cache")
            envelope.state = "DONE"

            return {
                "status": "COMPLETED",
                "delivery_id": envelope.delivery_id,
                "message_id": envelope.message_id,
                "task_id": envelope.task_id,
                "requested_target_agent": requested_target_agent,
                "effective_target_agent": effective_target_agent,
                "routing_reason": routing_reason,
                "execution_class": exec_class,
                "reused_from_cache": True,
                "chief_delivery": "PREPARED_NOT_DELIVERED"
            }

        # Single-owner claim lease
        acquired, lease_reason, lease_data = lease_manager.acquire_lease(
            task_id=envelope.task_id,
            task_hash=task_hash,
            owner_id=f"courier-{effective_target_agent}-bridge",
        )
        if not acquired:
            self.inbox.record_rejected(envelope, "DUPLICATE_TASK_DISPATCH_BLOCKED")
            return {
                "status": "BLOCKED_DUPLICATE_TASK_CLAIM",
                "reason": "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER",
                "owner_id": lease_data.get("owner_id")
            }

        # 5. Transition to DISPATCHED
        self.inbox.ledger.record_transition(envelope, prior_state="DISPATCHABLE", next_state="DISPATCHED", reason=f"Dispatched to builder {effective_target_agent}")
        envelope.state = "DISPATCHED"

        # 6. Bounded Execution via Level 6 Loop (max_iterations = 1)
        try:
            loop_engine = AutonomousLevel6Loop(repo_dir=self.repo_dir, max_iterations=1)
            plan_step = {
                "task_id": envelope.task_id,
                "instruction": instruction,
                "allowed_scope": allowed_scope,
                "target_agent": effective_target_agent,
                "routing_reason": routing_reason,
                "context_delta": payload.get("context_package", {}).get("context_delta"),
                "context_version": payload.get("context_package", {}).get("context_version", "v73"),
            }

            exec_summary = loop_engine.run_multi_round_workflow(
                workflow_id=f"WF-GH-{envelope.task_id}",
                workflow_plan=[plan_step],
                correlation_id=envelope.correlation_id,
            )
        except Exception as e:
            if "Workflow" in type(e).__name__ or "locked" in str(e).lower():
                self.inbox.record_rejected(envelope, "DUPLICATE_WORKFLOW_LOCKED")
                return {
                    "status": "BLOCKED_DUPLICATE_TASK_CLAIM",
                    "reason": "WORKFLOW_ALREADY_LOCKED_BY_ANOTHER_PROCESS"
                }
            raise
        finally:
            lease_manager.release_lease(envelope.task_id, f"courier-{effective_target_agent}-bridge")

        # 7. Record Lifecycle Transitions: RESULT_RECEIVED -> ACKED -> DONE
        self.inbox.ledger.record_transition(envelope, prior_state="DISPATCHED", next_state="RESULT_RECEIVED", reason="Worker execution completed and result captured")
        envelope.state = "RESULT_RECEIVED"

        self.inbox.record_ack(envelope.delivery_id, envelope.message_id, "PROCESSED")
        self.inbox.ledger.record_transition(envelope, prior_state="RESULT_RECEIVED", next_state="ACKED", reason="Delivery acknowledged")
        envelope.state = "ACKED"

        self.inbox.record_processed(envelope)
        self.inbox.ledger.record_transition(envelope, prior_state="ACKED", next_state="DONE", reason="Envelope fully processed and stored")
        envelope.state = "DONE"

        return {
            "status": "COMPLETED",
            "delivery_id": envelope.delivery_id,
            "message_id": envelope.message_id,
            "task_id": envelope.task_id,
            "requested_target_agent": requested_target_agent,
            "effective_target_agent": effective_target_agent,
            "routing_reason": routing_reason,
            "execution_class": exec_class,
            "execution_summary": exec_summary,
            "chief_delivery": "PREPARED_NOT_DELIVERED"
        }


class TransportResultReturnAdapter:
    """Converts worker results into canonical transport result envelopes with content-hash Thought Ingestion dedupe."""

    @staticmethod
    def package_result_envelope(
        task_id: str,
        correlation_id: str,
        result_payload: dict,
        source_agent: str = "courier-antigravity-bridge",
    ) -> GitHubTransportEnvelope:
        envelope = GitHubTransportEnvelope(
            schema_version="1.0",
            message_id=f"msg-res-{uuid.uuid4().hex[:12]}",
            delivery_id=f"deliv-res-{uuid.uuid4().hex[:12]}",
            correlation_id=correlation_id,
            task_id=task_id,
            event_type="RESULT",
            source=source_agent,
            target="thought-memory-mesh",
            repository="happyhippovip/2026-courier",
            ref="refs/heads/main",
            payload=result_payload,
            chief_delivery="PREPARED_NOT_DELIVERED",
            state="RESULT_RECEIVED"
        )
        return envelope

    @staticmethod
    def ingest_into_thought_pipeline(
        envelope: GitHubTransportEnvelope,
        repo_dir: Path | None = None,
    ) -> dict[str, Any]:
        from scripts.run_thought_ingestion import canonical_hash

        base = repo_dir or COURIER_DIR
        thought_incoming = base / "events" / "thought-incoming"
        thought_processed = base / "events" / "thought-processed"
        thought_incoming.mkdir(parents=True, exist_ok=True)
        thought_processed.mkdir(parents=True, exist_ok=True)

        content_dict = {
            "task_id": envelope.task_id,
            "correlation_id": envelope.correlation_id,
            "event_type": envelope.event_type,
            "summary": envelope.payload.get("summary", f"Result for {envelope.task_id}"),
            "verdict": envelope.payload.get("verdict", "ACCEPTED"),
        }
        content_hash = canonical_hash(content_dict)

        # Deterministic content-addressed artifact filename
        deterministic_filename = f"ingest-gh-res-{envelope.task_id}-{content_hash[:12]}.json"
        target_file = thought_incoming / deterministic_filename
        if target_file.exists():
            return {
                "status": "IDEMPOTENT_ALREADY_INGESTED",
                "ingestion_id": f"ingest-gh-res-{envelope.task_id}-{content_hash[:12]}",
                "file": str(target_file),
                "memory_write": "NONE",
                "chief_delivery": "PREPARED_NOT_DELIVERED"
            }

        # Content-hash scan across thought-incoming and thought-processed
        for folder in [thought_incoming, thought_processed]:
            for f in folder.glob("*.json"):
                data = load_json(f)
                if data and (data.get("content_hash") == content_hash or data.get("source_message_id") == envelope.message_id):
                    return {
                        "status": "IDEMPOTENT_ALREADY_INGESTED",
                        "ingestion_id": data.get("ingestion_id", deterministic_filename[:-5]),
                        "file": str(f),
                        "memory_write": "NONE",
                        "chief_delivery": "PREPARED_NOT_DELIVERED"
                    }

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ingestion_id = f"ingest-gh-res-{envelope.task_id}-{content_hash[:12]}"
        ingestion_payload = {
            "ingestion_id": ingestion_id,
            "source_type": "WORK_RESULT",
            "source_message_id": envelope.message_id,
            "source_timestamp": envelope.created_at,
            "received_at": now_iso,
            "content_hash": content_hash,
            "content": content_dict,
            "metadata": {
                "kind": "WORK_RESULT",
                "status_label": "VERIFIED_COMPLETED",
                "delivery_id": envelope.delivery_id,
                "correlation_id": envelope.correlation_id,
                "task_id": envelope.task_id,
            },
            "correlation_id": envelope.correlation_id,
            "privacy_class": "INTERNAL"
        }

        save_json_atomic(target_file, ingestion_payload)

        return {
            "status": "INGESTED_TO_THOUGHT_PIPELINE",
            "ingestion_id": ingestion_id,
            "file": str(target_file),
            "memory_write": "NONE",
            "chief_delivery": "PREPARED_NOT_DELIVERED"
        }

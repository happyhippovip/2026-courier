"""Worker Connection Contract, Runtime Identity & Execution Readiness (CP-17 / P17)

Enforces strict separation between:
1. OPEN_AVAILABLE: UI window, terminal, or browser session physically open/visible.
   Has OS process/window identity, but zero authenticated communication with Hub.
   CANNOT claim or execute tasks.
2. CONNECTED: Worker process with verified cryptographic session & live heartbeat.
   Connected to Hub, but may lack a supported task execution adapter.
   CANNOT execute tasks unless adapter is verified.
3. EXECUTION_CAPABLE: Worker is CONNECTED AND has a verified ExecutionAdapter
   implementing the required interface for the target capability.
   CAN claim, execute bounded work, and return verified DurableResult.

Failure Invariants:
- A missing or unverified adapter is strictly classified as CAPABILITY_MISSING.
- Zero fake-PASS: CAPABILITY_MISSING strictly fails closed and NEVER speculates success.
- Open UI window != CONNECTED != EXECUTION_CAPABLE.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


class WorkerState(str, enum.Enum):
    OPEN_AVAILABLE = "OPEN_AVAILABLE"
    CONNECTED = "CONNECTED"
    EXECUTION_CAPABLE = "EXECUTION_CAPABLE"
    CAPABILITY_MISSING = "CAPABILITY_MISSING"
    DISCONNECTED = "DISCONNECTED"


class CapabilityMissingError(RuntimeError):
    """Raised when an attempt is made to execute work without a verified adapter."""


@dataclass
class SurfaceIdentity:
    """Observable identity of an open UI window or desktop surface."""
    surface_id: str
    window_title: str
    pid: int
    create_time: float
    is_visible: bool = True
    state: str = "OPEN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "window_title": self.window_title,
            "pid": self.pid,
            "create_time": self.create_time,
            "is_visible": self.is_visible,
            "state": self.state,
        }


@dataclass
class RuntimeIdentity:
    """Verifiable cryptographic session and process identity of a connected worker."""
    worker_id: str
    session_id: str
    pid: int
    create_time: float
    host: str
    platform: str
    auth_fingerprint: str  # SHA-256 digest of credential token (never raw secret)
    last_heartbeat: float = field(default_factory=time.time)

    def is_live(self, ttl_seconds: float = 300.0) -> bool:
        """Verify the session heartbeat is within the allowed TTL window."""
        return (time.time() - self.last_heartbeat) < ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "session_id": self.session_id,
            "pid": self.pid,
            "create_time": self.create_time,
            "host": self.host,
            "platform": self.platform,
            "auth_fingerprint": self.auth_fingerprint,
            "last_heartbeat": self.last_heartbeat,
        }

    @classmethod
    def create(cls, worker_id: str, session_id: str, pid: int, create_time: float,
               host: str, platform: str, token: str) -> RuntimeIdentity:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        return cls(
            worker_id=worker_id,
            session_id=session_id,
            pid=pid,
            create_time=create_time,
            host=host,
            platform=platform,
            auth_fingerprint=token_hash,
            last_heartbeat=time.time(),
        )


@dataclass
class AdapterContract:
    """Task/Result contract and capability interface exposed by an execution adapter."""
    adapter_name: str
    supported_interface: str  # e.g., 'run_task_v1', 'muse_v1', 'shell_v1'
    supported_capabilities: List[str]
    effect_classes: Dict[str, str] = field(default_factory=dict)  # cap -> 'idempotent' | 'non_idempotent'
    is_ready_probe: Optional[Callable[[], bool]] = None

    def verify_readiness(self) -> bool:
        """Deterministic probe checking whether adapter dependencies/runtimes are present."""
        if self.is_ready_probe is not None:
            try:
                return bool(self.is_ready_probe())
            except Exception:
                return False
        return True

    def can_execute(self, capability: str) -> bool:
        """Check if this adapter declares and can execute the specified capability."""
        if not self.verify_readiness():
            return False
        return capability.lower().strip() in {c.lower().strip() for c in self.supported_capabilities}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "supported_interface": self.supported_interface,
            "supported_capabilities": list(self.supported_capabilities),
            "effect_classes": dict(self.effect_classes),
        }


@dataclass
class WorkerReadinessReport:
    """Audit report classifying worker readiness and distinguishing open UI from execution capability."""
    worker_id: str
    state: WorkerState
    can_execute: bool
    reason: str
    surface: Optional[SurfaceIdentity] = None
    runtime_identity: Optional[RuntimeIdentity] = None
    adapter: Optional[AdapterContract] = None
    requested_capability: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "state": self.state.value,
            "can_execute": self.can_execute,
            "reason": self.reason,
            "surface": self.surface.to_dict() if self.surface else None,
            "runtime_identity": self.runtime_identity.to_dict() if self.runtime_identity else None,
            "adapter": self.adapter.to_dict() if self.adapter else None,
            "requested_capability": self.requested_capability,
        }


class WorkerVerificationEngine:
    """Verifies that an open surface, connected session, and execution adapter satisfy the contract."""

    @staticmethod
    def evaluate_readiness(
        worker_id: str,
        surface: Optional[SurfaceIdentity] = None,
        connection: Optional[RuntimeIdentity] = None,
        adapter: Optional[AdapterContract] = None,
        requested_capability: Optional[str] = None,
        heartbeat_ttl_s: float = 300.0,
    ) -> WorkerReadinessReport:
        """Evaluate worker readiness while strictly separating OPEN_AVAILABLE, CONNECTED, and EXECUTION_CAPABLE."""
        # 1. Connection check: No live session
        if connection is None or not connection.is_live(ttl_seconds=heartbeat_ttl_s):
            if surface is not None and surface.is_visible:
                # Open UI window exists, but zero authenticated Hub connection
                return WorkerReadinessReport(
                    worker_id=worker_id,
                    state=WorkerState.OPEN_AVAILABLE,
                    can_execute=False,
                    reason="Surface window is open and visible locally, but worker has no authenticated Hub connection.",
                    surface=surface,
                    runtime_identity=connection,
                    adapter=adapter,
                    requested_capability=requested_capability,
                )
            return WorkerReadinessReport(
                worker_id=worker_id,
                state=WorkerState.DISCONNECTED,
                can_execute=False,
                reason="Worker session is disconnected or heartbeat has expired.",
                surface=surface,
                runtime_identity=connection,
                adapter=adapter,
                requested_capability=requested_capability,
            )

        # 2. Worker is CONNECTED: Now check execution adapter
        if adapter is None:
            return WorkerReadinessReport(
                worker_id=worker_id,
                state=WorkerState.CAPABILITY_MISSING,
                can_execute=False,
                reason="Worker is connected, but has no execution adapter registered (CAPABILITY_MISSING).",
                surface=surface,
                runtime_identity=connection,
                adapter=None,
                requested_capability=requested_capability,
            )

        # 3. Adapter readiness probe
        if not adapter.verify_readiness():
            return WorkerReadinessReport(
                worker_id=worker_id,
                state=WorkerState.CAPABILITY_MISSING,
                can_execute=False,
                reason=f"Adapter '{adapter.adapter_name}' failed local readiness probe.",
                surface=surface,
                runtime_identity=connection,
                adapter=adapter,
                requested_capability=requested_capability,
            )

        # 4. Capability coverage check
        if requested_capability is not None:
            cap_norm = requested_capability.strip().lower()
            supported = {c.strip().lower() for c in adapter.supported_capabilities}
            if cap_norm not in supported:
                return WorkerReadinessReport(
                    worker_id=worker_id,
                    state=WorkerState.CAPABILITY_MISSING,
                    can_execute=False,
                    reason=f"Adapter '{adapter.adapter_name}' does not declare capability '{requested_capability}'.",
                    surface=surface,
                    runtime_identity=connection,
                    adapter=adapter,
                    requested_capability=requested_capability,
                )

        # 5. All criteria met: Worker is EXECUTION_CAPABLE (arbeitsfähig)
        return WorkerReadinessReport(
            worker_id=worker_id,
            state=WorkerState.EXECUTION_CAPABLE,
            can_execute=True,
            reason="Worker has verified runtime identity and adapter implements the requested capability.",
            surface=surface,
            runtime_identity=connection,
            adapter=adapter,
            requested_capability=requested_capability,
        )

    @staticmethod
    def enforce_no_fake_pass(report: WorkerReadinessReport) -> None:
        """Fail closed: Throws CapabilityMissingError if execution is attempted without capability."""
        if not report.can_execute:
            raise CapabilityMissingError(
                f"CANNOT_EXECUTE: Worker '{report.worker_id}' is in state {report.state.value} ({report.reason}). "
                "Fake-PASS is strictly prohibited."
            )

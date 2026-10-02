"""Courier v1 worker host: bounded execution of one claimed attempt (lane L3).

The host owns exactly one live dispatch at a time and runs its command as a
contained child process: bounded lifetime, bounded timeout, explicit
cancellation, owned-tree cleanup, no orphans, no polling storms, no retries.
Every abnormal end (crash, timeout, cancel, lost lease) becomes a durable
result with evidence, never silence. Resource pressure and file-descriptor
exhaustion pause the host instead of spinning.

The journal stays the controller's: this package never imports, opens or
writes the journal. Results are delivered to the controller (lane L2,
``courier_core.serve``) through :mod:`courier_worker.service`; the payloads
it sends are shaped so the L2 event validator accepts them unchanged.
"""

from courier_worker.host import (
    ContainmentError,
    ExecutionResult,
    ExecutionSpec,
    HostBusy,
    Outcome,
    ResourcePaused,
    SpecError,
    WorkerHost,
    acquire_home_lock,
    default_pressure_probe,
    release_home_lock,
    run_orphan_gate,
)

__all__ = [
    "ContainmentError",
    "ExecutionResult",
    "ExecutionSpec",
    "HostBusy",
    "Outcome",
    "ResourcePaused",
    "SpecError",
    "WorkerHost",
    "acquire_home_lock",
    "default_pressure_probe",
    "release_home_lock",
    "run_orphan_gate",
]

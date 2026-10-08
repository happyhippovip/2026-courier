"""Test hardening for courier_worker package init (P9-worker_init).

Covers only the re-export contract in courier_worker/__init__.py:
names listed in __all__ exist, are identical to courier_worker.host
objects, and error/constant contracts hold. No behavior change, no
network, no credentials.
"""

from __future__ import annotations

import courier_worker
import courier_worker.host as host_mod


EXPECTED_ALL = frozenset({
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
})


def test_all_lists_exactly_expected_names():
    assert frozenset(courier_worker.__all__) == EXPECTED_ALL


def test_all_entries_unique_strings():
    assert all(isinstance(n, str) for n in courier_worker.__all__)
    assert len(courier_worker.__all__) == len(set(courier_worker.__all__))


def test_reexports_are_host_identities():
    for name in courier_worker.__all__:
        assert hasattr(host_mod, name), name
        assert getattr(courier_worker, name) is getattr(host_mod, name), name


def test_package_docstring_present():
    assert isinstance(courier_worker.__doc__, str)
    assert "single" in courier_worker.__doc__.lower() or "bounded" in courier_worker.__doc__.lower()


def test_error_hierarchy():
    assert issubclass(courier_worker.SpecError, ValueError)
    assert issubclass(courier_worker.HostBusy, RuntimeError)
    assert issubclass(courier_worker.ResourcePaused, RuntimeError)
    assert issubclass(courier_worker.ContainmentError, RuntimeError)
    assert courier_worker.ResourcePaused("fd-exhaustion").reason == "fd-exhaustion"


def test_outcome_constants():
    assert courier_worker.Outcome.COMPLETED == "completed"
    assert courier_worker.Outcome.CRASH == "crash"
    assert courier_worker.Outcome.TIMEOUT == "timeout"
    assert courier_worker.Outcome.CANCELLED == "cancelled"
    assert courier_worker.Outcome.LEASE_LOST == "lease-lost"
    assert courier_worker.Outcome.SPAWN_FAILED == "spawn-failed"


def test_outcome_retryable_shape():
    assert isinstance(courier_worker.Outcome, type)


def test_default_pressure_probe_returns_none_or_reason():
    result = courier_worker.default_pressure_probe()
    assert result is None or isinstance(result, str)
    if isinstance(result, str):
        assert result


def test_acquire_release_home_lock_roundtrip(tmp_path):
    home = str(tmp_path / "home")
    fd = courier_worker.acquire_home_lock(home)
    try:
        assert isinstance(fd, int)
    finally:
        courier_worker.release_home_lock(fd)
    # Re-acquire after release works (no stale lock).
    fd2 = courier_worker.acquire_home_lock(home)
    try:
        assert isinstance(fd2, int)
    finally:
        courier_worker.release_home_lock(fd2)


def test_run_orphan_gate_empty_home_returns_zero(tmp_path):
    assert courier_worker.run_orphan_gate(str(tmp_path / "empty-home")) == 0


def test_host_only_names_not_reexported():
    # LivenessState/OutboxFull exist on host but are intentionally not
    # part of the package surface.
    assert not hasattr(courier_worker, "LivenessState") or "LivenessState" not in courier_worker.__all__
    assert "OutboxFull" not in courier_worker.__all__


def test_no_journal_attribute_on_package():
    assert not hasattr(courier_worker, "Journal")
    assert not hasattr(courier_worker, "journal")

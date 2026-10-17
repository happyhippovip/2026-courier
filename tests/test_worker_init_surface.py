"""P9 test hardening for courier_worker package surface (P9-worker_init_surface).

Covers only the import surface in courier_worker/__init__.py: __all__
ordering, star-import exactness, package identity, import isolation
(no courier_core/journal/controller/adapter imports), callable surface,
error-hierarchy disjointness, Outcome constants shape, and orphan-gate
return shape. No behavior change, no network, no credentials.
"""

from __future__ import annotations

import dataclasses
import enum
import subprocess
import sys
from pathlib import Path

import courier_worker
import courier_worker.host as host_mod

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ALL_ORDERED = [
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


def test_all_is_sorted_list_with_expected_order():
    assert isinstance(courier_worker.__all__, list)
    assert courier_worker.__all__ == EXPECTED_ALL_ORDERED
    assert sorted(courier_worker.__all__) == list(courier_worker.__all__)


def test_dir_contains_every_all_entry():
    names = set(dir(courier_worker))
    for name in courier_worker.__all__:
        assert name in names, name


def test_star_import_exposes_exactly_all():
    namespace: dict = {}
    exec("from courier_worker import *", namespace)
    exposed = {k for k in namespace if not k.startswith("_")}
    assert exposed == set(courier_worker.__all__)


def test_package_identity():
    assert courier_worker.__name__ == "courier_worker"
    assert courier_worker.__package__ == "courier_worker"
    assert isinstance(courier_worker.__path__, list)
    assert isinstance(courier_worker.__doc__, str)
    assert courier_worker.__doc__.strip()


def test_fresh_import_loads_only_worker_modules():
    code = (
        "import sys, courier_worker; "
        "print(','.join(sorted(m for m in sys.modules if m.startswith('courier'))))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert proc.stdout.strip().split(",") == ["courier_worker", "courier_worker.host"]


def test_fresh_import_pulls_no_controller_or_adapter_modules():
    code = (
        "import sys, courier_worker; "
        "mods = set(sys.modules); "
        "print('controller' in str(sorted(mods))); "
        "print(any('adapter' in m for m in mods)); "
        "print(any(m.startswith('courier_core') for m in mods)); "
        "print(any('journal' in m for m in mods))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert proc.stdout.strip().splitlines() == ["False", "False", "False", "False"]


def test_reexported_functions_are_callable():
    for name in (
        "acquire_home_lock",
        "default_pressure_probe",
        "release_home_lock",
        "run_orphan_gate",
    ):
        assert callable(getattr(courier_worker, name)), name
        assert getattr(courier_worker, name) is getattr(host_mod, name), name


def test_reexported_classes_are_types():
    for name in (
        "ContainmentError",
        "ExecutionResult",
        "ExecutionSpec",
        "HostBusy",
        "Outcome",
        "ResourcePaused",
        "SpecError",
        "WorkerHost",
    ):
        assert isinstance(getattr(courier_worker, name), type), name


def test_execution_types_are_dataclasses():
    assert dataclasses.is_dataclass(courier_worker.ExecutionSpec)
    assert dataclasses.is_dataclass(courier_worker.ExecutionResult)
    assert not isinstance(courier_worker.WorkerHost, enum.EnumMeta)


def test_error_hierarchy_is_disjoint():
    assert issubclass(courier_worker.SpecError, ValueError)
    assert not issubclass(courier_worker.SpecError, RuntimeError)
    for name in ("HostBusy", "ContainmentError", "ResourcePaused"):
        cls = getattr(courier_worker, name)
        assert issubclass(cls, RuntimeError), name
        assert not issubclass(cls, ValueError), name


def test_outcome_members_are_distinct_strings():
    values = [
        courier_worker.Outcome.COMPLETED,
        courier_worker.Outcome.CRASH,
        courier_worker.Outcome.TIMEOUT,
        courier_worker.Outcome.CANCELLED,
        courier_worker.Outcome.LEASE_LOST,
        courier_worker.Outcome.SPAWN_FAILED,
    ]
    assert all(isinstance(v, str) for v in values)
    assert len(set(values)) == len(values)
    assert not isinstance(courier_worker.Outcome, enum.EnumMeta)


def test_package_exposes_no_credential_named_attributes():
    lowered = {n.lower() for n in dir(courier_worker)}
    for banned in ("token", "secret", "password", "credential", "api_key", "apikey"):
        assert banned not in lowered, banned


def test_run_orphan_gate_missing_nested_returns_int(tmp_path):
    target = str(tmp_path / "nope" / "nested" / "home")
    result = courier_worker.run_orphan_gate(target)
    assert isinstance(result, int)
    assert result == 0

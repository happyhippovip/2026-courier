"""P9 hardening pins for the courier_worker package surface.

Scope: tests only, no behavior change. Pins ``courier_worker/__init__.py``
re-export discipline over :mod:`courier_worker.host`: exact export set,
identity with the host objects, sorted/deduplicated ``__all__``, and no
implicit import of the wiring layers (service/adapter_bridge) on a fresh
``import courier_worker``. Offline; no network, no filesystem writes.
"""

import importlib
import subprocess
import sys


EXPECTED_EXPORTS = frozenset(
    {
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
    }
)


def test_all_matches_expected_export_set():
    import courier_worker

    assert set(courier_worker.__all__) == set(EXPECTED_EXPORTS)
    assert len(courier_worker.__all__) == len(EXPECTED_EXPORTS)


def test_all_is_sorted_and_deduplicated():
    import courier_worker

    assert list(courier_worker.__all__) == sorted(courier_worker.__all__)


def test_exports_are_identical_to_host_objects():
    import courier_worker
    import courier_worker.host as host

    for name in EXPECTED_EXPORTS:
        assert hasattr(courier_worker, name), name
        assert getattr(courier_worker, name) is getattr(host, name), name


def test_public_surface_is_exports_plus_host_submodule():
    import courier_worker

    public = {n for n in dir(courier_worker) if not n.startswith("_")}
    assert public == set(EXPECTED_EXPORTS) | {"host"}


def test_expected_names_cover_key_host_callables():
    import courier_worker

    assert callable(courier_worker.WorkerHost)
    assert callable(courier_worker.acquire_home_lock)
    assert callable(courier_worker.release_home_lock)
    assert callable(courier_worker.default_pressure_probe)
    assert callable(courier_worker.run_orphan_gate)


def test_fresh_import_does_not_pull_wiring_layers():
    script = (
        "import sys, courier_worker; "
        "print('courier_worker.host' in sys.modules); "
        "print('courier_worker.service' in sys.modules); "
        "print('courier_worker.adapter_bridge' in sys.modules)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert lines == ["True", "False", "False"]


def test_reimport_keeps_export_identity():
    import courier_worker
    import courier_worker.host as host

    reloaded_pkg = importlib.import_module("courier_worker")
    assert reloaded_pkg is courier_worker
    for name in EXPECTED_EXPORTS:
        assert getattr(reloaded_pkg, name) is getattr(host, name), name

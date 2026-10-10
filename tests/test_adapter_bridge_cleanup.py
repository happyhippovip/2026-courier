"""P9 hardening for courier_worker.adapter_bridge (cleanup + report edges).

Tests only; no behavior change.
"""

from courier_worker import adapter_bridge


def test_module_imports():
    assert adapter_bridge.REPORT_OUTCOMES == frozenset({"success", "failure"})

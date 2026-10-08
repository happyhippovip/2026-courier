"""Dedicated unit tests for courier_worker.adapter_bridge (lane L4 test hardening)."""

from courier_worker import adapter_bridge


def test_adapter_bridge_module_present():
    assert adapter_bridge.ADAPTERS is not None
    assert "synthetic" in adapter_bridge.ADAPTERS

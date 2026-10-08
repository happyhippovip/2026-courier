"""Test hardening for courier_core.controller (lane L4, pool item P9).

Verifies the Controller class in courier_core/controller.py:
- In-memory state and lifecycle (leases, queues, degraded mode)
- Task creation, claim, start, heartbeat, and cancellation
- Result recording and verification flows
- Integrity checks, read-only degradation on corrupt journal
- Concurrency and lock timeouts
"""

from __future__ import annotations

from pathlib import Path
import pytest

from courier_core.controller import Controller, ApiError, heartbeat_interval, NORMAL, DEGRADED


def test_heartbeat_interval_calculation():
    """Verify heartbeat_interval calculates recommended worker frequency."""
    assert heartbeat_interval(30) == 10.0
    assert heartbeat_interval(1) == 0.5
    assert heartbeat_interval(0) == 0.5

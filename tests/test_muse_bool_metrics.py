"""Bool metrics are not a host reading and must not admit slots."""

import pytest

pytest.importorskip("fcntl")

from scripts.mac_worker.muse_supervisor import CapacityGovernor


def test_bool_metrics_do_not_admit():
    gov = CapacityGovernor(
        requested_max=4,
        clock=lambda: 0,
        reader=lambda: {"swap_mb": True, "load_1m": True, "mem_free_pct": 80.0},
    )
    assert gov.evaluate() == 0
    assert gov.state == "HOLD"

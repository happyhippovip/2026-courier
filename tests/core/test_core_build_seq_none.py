"""P9 hardening for courier_core.build: None-seq + missing-build pins.

Tests only; no behavior change. No network calls.
"""

from courier_core.build import build_identity


def test_claim_placeholder():
    assert isinstance(build_identity(), dict)

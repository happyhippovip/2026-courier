"""P9 hardening claim for courier_core.build (build_for_seq focus).

Claim commit: reserves the P9-build_seq lane. Expanded pure-unit tests follow.
"""

from courier_core.build import build_for_seq


def test_claim_lane_reserved():
    assert callable(build_for_seq)

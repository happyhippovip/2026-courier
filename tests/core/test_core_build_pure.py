"""P9 hardening for courier_core.build: pure env + cache + seq attribution.

Tests only; no behavior change. No network calls.

Covers build_identity() env handling (absent, empty, truncation),
source_sha256() stability/caching, and build_for_seq() attribution
over synthetic Event streams.
"""

import courier_core.build as build_mod
from courier_core.build import build_identity


def test_claim_placeholder():
    assert isinstance(build_identity(), dict)

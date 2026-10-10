"""P9 hardening placeholder for courier_core.verification reason/version bounds.

Full pins follow; this initial commit only claims the branch.
"""

from courier_core.verification import Verdict


def test_verdict_defaults_claim():
    v = Verdict(False)
    assert v.accepted is False
    assert v.reason == ""
    assert v.retryable is False
    assert v.verifier is None

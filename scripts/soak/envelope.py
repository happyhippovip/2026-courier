"""Pass rule for the host-guardian soak verdict.

Kept separate from the soak runner so the rule can be tested without the
optional host-capacity sampler.
"""


def envelope_pass(verdict: dict) -> bool:
    """A soak passes only when every envelope key is an explicit True.

    A missing object-growth or file-descriptor sample is not inside the
    envelope.
    """
    if not isinstance(verdict, dict):
        return False
    return (
        verdict.get("obj_within_envelope") is True
        and verdict.get("fd_within_envelope") is True
        and verdict.get("probes_within_envelope") is True
    )

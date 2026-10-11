"""Update Capability Gate: an update is accepted only if it keeps every accepted capability.

BEFORE = accepted capabilities of the installed version (criterion -> passed)
plus a replay digest of a fixed synthetic commitment. The candidate is
exercised side by side on a copy of the user's data; AFTER is measured the
same way. LOST capabilities reject the update; NEW ones are only PROPOSED
until they are evidenced (same rule as the Semantic Delta ADR); a changed
replay digest means the journal no longer projects to the same history and
rejects. A rejection carries the recovery information to stay on BEFORE.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityState:
    version: str
    capabilities: dict        # criterion id -> True when evidenced on this version
    replay_digest: str        # hash of the canonical projection of a fixed journal


def compare(before, after):
    accepted_before = {c for c, ok in before.capabilities.items() if ok}
    accepted_after = {c for c, ok in after.capabilities.items() if ok}
    lost = sorted(accepted_before - accepted_after)
    new = sorted(accepted_after - accepted_before)
    replay_ok = before.replay_digest == after.replay_digest
    if lost or not replay_ok:
        reasons = [f"lost: {lost}"] if lost else []
        if not replay_ok:
            reasons.append("journal replay projects to a different history")
        return {"decision": "REJECT", "lost": lost, "proposed": new, "reasons": reasons,
                "recovery": {"keep_version": before.version, "discard_version": after.version,
                             "action": "RESUME_FROM_CHECKPOINT", "resume_from": {"version": before.version}}}
    return {"decision": "ACCEPT", "lost": [], "proposed": new,
            "reasons": [f"kept all {len(accepted_before)} accepted capabilities"] +
                       ([f"{len(new)} new capabilities proposed, not yet accepted"] if new else []),
            "switch_to": after.version}

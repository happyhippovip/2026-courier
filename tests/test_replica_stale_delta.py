"""Replica delta validation: fence + hash chain enforced, replays deduped.

Covers courier_core/replica_coordinator.py apply_deltas: a delta on the
expected sequence with a stale fence or a broken hash link raises
StaleDeltaError; already-seen or future sequences stay skipped (dedupe).
"""
import hashlib
import json

import pytest

from courier_core.replica_coordinator import (
    ReplicaCoordinator,
    ReplicationMutation,
    StaleDeltaError,
)


def _commit(seq, fence, prev, payload):
    content = f"{seq}:{fence}:{prev}:{json.dumps(payload, sort_keys=True)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _fresh_pair():
    leader = ReplicaCoordinator(node_id="leader-0")
    leader.propose_mutation(payload={"step": 1}, fence_token=100)
    follower = ReplicaCoordinator(node_id="peer-1")
    return leader, follower


def test_valid_catchup_still_applies():
    leader, follower = _fresh_pair()
    leader.propose_mutation(payload={"step": 2}, fence_token=101)
    applied = follower.apply_deltas(leader.get_delta_catchup(from_sequence=0))
    assert applied == 2
    assert follower.current_sequence == 2


def test_stale_fence_on_expected_sequence_raises():
    leader, follower = _fresh_pair()
    follower.apply_deltas(leader.get_delta_catchup(from_sequence=0))
    prev = follower.log[-1].commit_hash
    stale = ReplicationMutation(
        sequence_id=2, fence_token=50, payload={"evil": True}, committed=True,
    )
    stale.commit_hash = _commit(2, 50, prev, {"evil": True})
    with pytest.raises(StaleDeltaError):
        follower.apply_deltas([stale])
    assert follower.current_sequence == 1


def test_broken_hash_chain_raises():
    leader, follower = _fresh_pair()
    follower.apply_deltas(leader.get_delta_catchup(from_sequence=0))
    tampered = ReplicationMutation(
        sequence_id=2, fence_token=101, payload={"step": 2}, committed=True,
    )
    tampered.commit_hash = "0" * 64
    with pytest.raises(StaleDeltaError):
        follower.apply_deltas([tampered])
    assert follower.current_sequence == 1


def test_replay_and_future_gap_are_skipped_not_rejected():
    leader, follower = _fresh_pair()
    assert follower.apply_deltas(leader.get_delta_catchup(from_sequence=0)) == 1
    assert follower.apply_deltas(leader.get_delta_catchup(from_sequence=0)) == 0
    future = ReplicationMutation(
        sequence_id=9, fence_token=999, payload={}, committed=True,
    )
    future.commit_hash = "0" * 64
    assert follower.apply_deltas([future]) == 0
    assert follower.current_sequence == 1

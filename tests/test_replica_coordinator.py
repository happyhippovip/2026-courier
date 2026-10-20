"""Tests for courier_core.replica_coordinator (Multi-Node Geo-Fence Replica Coordinator)."""

import json
import pytest
from datetime import datetime, timezone
from courier_core.replica_coordinator import (
    ReplicaCoordinator,
    PeerNode,
    PeerStatus,
    ReplicationMutation,
    QuorumUnavailableError,
    DivergentBranchConflictError,
    main,
)


def test_peer_registration_and_quorum_calculation(tmp_path):
    store_file = tmp_path / "coordinator_state.json"
    coord = ReplicaCoordinator(node_id="coordinator-0", store_path=str(store_file))

    # Register 3 peers
    coord.register_peer("peer-win-1", "http://10.0.0.1:8000")
    coord.register_peer("peer-linux-1", "http://10.0.0.2:8000")
    coord.register_peer("peer-mac-1", "http://10.0.0.3:8000")

    assert len(coord.peers) == 3
    # Total cluster size = 1 (local) + 3 (peers) = 4 -> quorum is (4 // 2) + 1 = 3
    assert coord.calculate_quorum() == 3
    assert coord.active_node_count() == 4


def test_replicate_mutation_reaches_quorum(tmp_path):
    coord = ReplicaCoordinator(node_id="leader-0", store_path=str(tmp_path / "rep.json"))
    coord.register_peer("peer-1", "http://10.0.0.1:8000")
    coord.register_peer("peer-2", "http://10.0.0.2:8000")

    # Cluster size = 3 (leader + 2 peers) -> quorum is 2
    assert coord.calculate_quorum() == 2

    # Propose mutation
    commit = coord.propose_mutation(
        payload={"action": "CLAIM", "item_id": "P57", "holder": "worker-1"},
        fence_token=105,
        mock_ack_nodes=["leader-0", "peer-1"]  # 2 acks >= quorum 2
    )

    assert commit.committed is True
    assert commit.sequence_id == 1
    assert commit.ack_count == 2
    assert commit.commit_hash != ""
    assert coord.current_sequence == 1


def test_fail_closed_when_quorum_lost(tmp_path):
    coord = ReplicaCoordinator(node_id="leader-0", store_path=str(tmp_path / "rep.json"))
    coord.register_peer("peer-1", "http://10.0.0.1:8000")
    coord.register_peer("peer-2", "http://10.0.0.2:8000")

    # Mark peer-1 and peer-2 as unreachable
    coord.set_peer_status("peer-1", PeerStatus.UNREACHABLE)
    coord.set_peer_status("peer-2", PeerStatus.UNREACHABLE)

    # Active node count = 1 (leader only) < quorum (2)
    with pytest.raises(QuorumUnavailableError) as exc:
        coord.propose_mutation(
            payload={"action": "RELEASE", "item_id": "P57"},
            fence_token=106,
        )
    assert "Quorum unavailable" in str(exc.value)


def test_anti_entropy_delta_catchup(tmp_path):
    coord = ReplicaCoordinator(node_id="leader-0", store_path=str(tmp_path / "rep.json"))
    coord.register_peer("peer-lagging", "http://10.0.0.5:8000")

    # Commit 4 mutations
    for i in range(1, 5):
        coord.propose_mutation(
            payload={"step": i, "data": f"delta_{i}"},
            fence_token=100 + i,
            mock_ack_nodes=["leader-0", "peer-lagging"],
        )

    assert coord.current_sequence == 4

    # Peer is at sequence 2, needs catchup for [3, 4]
    deltas = coord.get_delta_catchup(from_sequence=2)
    assert len(deltas) == 2
    assert deltas[0].sequence_id == 3
    assert deltas[1].sequence_id == 4

    # Remote replica is at sequence 2, then applies deltas [3, 4]
    remote = ReplicaCoordinator(node_id="peer-lagging", store_path=str(tmp_path / "remote.json"))
    remote.apply_deltas(coord.get_delta_catchup(from_sequence=0)[:2])
    assert remote.current_sequence == 2

    applied = remote.apply_deltas(deltas)
    assert applied == 2
    assert remote.current_sequence == 4


def test_split_brain_resolution_via_fence_token(tmp_path):
    coord = ReplicaCoordinator(node_id="node-a", store_path=str(tmp_path / "a.json"))

    # Initial commit
    coord.propose_mutation(payload={"step": 1}, fence_token=200, mock_ack_nodes=["node-a"])

    # Competing mutation at sequence 2 with stale fence_token 190
    stale_mut = ReplicationMutation(
        sequence_id=2,
        fence_token=190,
        payload={"split": "branch_stale"},
        committed=True,
    )

    # Valid mutation at sequence 2 with higher fence_token 250
    fresh_mut = ReplicationMutation(
        sequence_id=2,
        fence_token=250,
        payload={"split": "branch_fresh"},
        committed=True,
    )

    # Resolving divergence: fresh must defeat stale
    winner = coord.resolve_divergence(local=stale_mut, remote=fresh_mut)
    assert winner.fence_token == 250
    assert winner.payload["split"] == "branch_fresh"


def test_cli_replica_coordinator(tmp_path, capsys):
    state_file = tmp_path / "cli_coord.json"

    # Status CLI
    rc1 = main(["--store", str(state_file), "--node-id", "win-lead", "status"])
    assert rc1 == 0
    assert "win-lead" in capsys.readouterr().out

    # Register peer CLI
    rc2 = main(["--store", str(state_file), "peer-add", "--peer-id", "linux-rep", "--url", "http://10.0.0.12:9000"])
    assert rc2 == 0
    assert "REGISTERED" in capsys.readouterr().out

    # Propose mutation CLI
    rc3 = main([
        "--store", str(state_file),
        "propose",
        "--action", "LEASE",
        "--item-id", "ITEM_99",
        "--fence-token", "300",
    ])
    assert rc3 == 0
    assert "COMMITTED" in capsys.readouterr().out

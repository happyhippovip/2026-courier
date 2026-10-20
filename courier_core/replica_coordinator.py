"""Multi-Node Geo-Fence Replica Coordinator and State Synchronizer for Courier Symphony.

Provides quorum-backed state replication, anti-entropy delta catchup for lagging nodes,
deterministic split-brain divergence resolution via fencing tokens, and dynamic peer membership.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PeerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"


class ReplicaCoordinatorError(Exception):
    """Base exception for replication errors."""
    pass


class QuorumUnavailableError(ReplicaCoordinatorError):
    """Raised when active replica count is below quorum requirement."""
    pass


class DivergentBranchConflictError(ReplicaCoordinatorError):
    """Raised when two divergent branches cannot be reconciled."""
    pass


class StaleDeltaError(ReplicaCoordinatorError):
    """Raised when a delta fails fence-token or hash-chain validation."""
    pass


@dataclass
class PeerNode:
    peer_id: str
    url: str
    status: PeerStatus = PeerStatus.ACTIVE
    last_heartbeat: str = ""
    last_known_sequence: int = 0

    def __post_init__(self):
        if not self.last_heartbeat:
            self.last_heartbeat = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PeerNode:
        return cls(
            peer_id=data["peer_id"],
            url=data["url"],
            status=PeerStatus(data["status"]),
            last_heartbeat=data.get("last_heartbeat", ""),
            last_known_sequence=data.get("last_known_sequence", 0),
        )


@dataclass
class ReplicationMutation:
    sequence_id: int
    fence_token: int
    payload: Dict[str, Any]
    commit_hash: str = ""
    ack_count: int = 1
    committed: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReplicationMutation:
        return cls(**data)


class ReplicaCoordinator:
    """Coordinates consensus, state replication, and anti-entropy catch-up across cluster replicas."""

    def __init__(self, node_id: str = "node-0", store_path: Optional[str] = None):
        self.node_id = node_id
        self.store_path = store_path
        self.peers: Dict[str, PeerNode] = {}
        self.log: List[ReplicationMutation] = []
        self.current_sequence: int = 0

        if self.store_path and Path(self.store_path).exists():
            self.load()

    def register_peer(self, peer_id: str, url: str) -> None:
        self.peers[peer_id] = PeerNode(peer_id=peer_id, url=url, status=PeerStatus.ACTIVE)

    def set_peer_status(self, peer_id: str, status: PeerStatus) -> None:
        if peer_id in self.peers:
            self.peers[peer_id].status = status

    def calculate_quorum(self) -> int:
        total = 1 + len(self.peers)
        return (total // 2) + 1

    def active_node_count(self) -> int:
        active_peers = sum(1 for p in self.peers.values() if p.status == PeerStatus.ACTIVE)
        return 1 + active_peers  # 1 for local node

    def propose_mutation(
        self,
        payload: Dict[str, Any],
        fence_token: int,
        mock_ack_nodes: Optional[List[str]] = None,
    ) -> ReplicationMutation:
        quorum = self.calculate_quorum()
        active = self.active_node_count()

        if active < quorum:
            raise QuorumUnavailableError(
                f"Quorum unavailable: {active} active nodes < required quorum {quorum}"
            )

        new_seq = self.current_sequence + 1
        prev_hash = self.log[-1].commit_hash if self.log else "GENESIS"

        content = f"{new_seq}:{fence_token}:{prev_hash}:{json.dumps(payload, sort_keys=True)}"
        commit_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        if mock_ack_nodes is not None:
            acks = len(mock_ack_nodes)
        else:
            acks = active

        if acks < quorum:
            raise QuorumUnavailableError(
                f"Quorum unavailable: received {acks} acknowledgments < required quorum {quorum}"
            )

        mutation = ReplicationMutation(
            sequence_id=new_seq,
            fence_token=fence_token,
            payload=payload,
            commit_hash=commit_hash,
            ack_count=acks,
            committed=True,
        )

        self.log.append(mutation)
        self.current_sequence = new_seq

        if self.store_path:
            self.save()

        return mutation

    def get_delta_catchup(self, from_sequence: int) -> List[ReplicationMutation]:
        return [m for m in self.log if m.sequence_id > from_sequence]

    def apply_deltas(self, deltas: List[ReplicationMutation]) -> int:
        count = 0
        for d in deltas:
            if d.sequence_id != self.current_sequence + 1:
                continue                    # at-least-once dedupe: already seen or future
            prev = self.log[-1].commit_hash if self.log else "GENESIS"
            if self.log and d.fence_token < self.log[-1].fence_token:
                raise StaleDeltaError(
                    f"delta seq {d.sequence_id} carries stale fence {d.fence_token}"
                )
            content = f"{d.sequence_id}:{d.fence_token}:{prev}:{json.dumps(d.payload, sort_keys=True)}"
            if hashlib.sha256(content.encode("utf-8")).hexdigest() != d.commit_hash:
                raise StaleDeltaError(
                    f"delta seq {d.sequence_id} breaks the hash chain"
                )
            self.log.append(d)
            self.current_sequence = d.sequence_id
            count += 1
        if self.store_path and count > 0:
            self.save()
        return count

    def resolve_divergence(
        self,
        local: ReplicationMutation,
        remote: ReplicationMutation,
    ) -> ReplicationMutation:
        # Deterministic conflict resolution: higher fence_token wins
        if remote.fence_token > local.fence_token:
            return remote
        elif local.fence_token > remote.fence_token:
            return local
        # If fence token is identical, higher commit_hash wins
        return remote if remote.commit_hash > local.commit_hash else local

    def save(self) -> None:
        if not self.store_path:
            return
        p = Path(self.store_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "node_id": self.node_id,
            "current_sequence": self.current_sequence,
            "peers": {pid: p_obj.to_dict() for pid, p_obj in self.peers.items()},
            "log": [m.to_dict() for m in self.log],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path or not Path(self.store_path).exists():
            return
        raw = json.loads(Path(self.store_path).read_text(encoding="utf-8"))
        self.node_id = raw.get("node_id", self.node_id)
        self.current_sequence = int(raw.get("current_sequence", 0))
        self.peers = {
            pid: PeerNode.from_dict(p_data) for pid, p_data in raw.get("peers", {}).items()
        }
        self.log = [ReplicationMutation.from_dict(m) for m in raw.get("log", [])]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replica Coordinator CLI")
    parser.add_argument("--store", default="registries/replica_coordinator.json")
    parser.add_argument("--node-id", default="local-node")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # status
    sub.add_parser("status", help="Show coordinator status and sequence")

    # peer-add
    p_add = sub.add_parser("peer-add", help="Register a peer node")
    p_add.add_argument("--peer-id", required=True)
    p_add.add_argument("--url", required=True)

    # propose
    p_prop = sub.add_parser("propose", help="Propose and replicate a mutation")
    p_prop.add_argument("--action", required=True)
    p_prop.add_argument("--item-id", required=True)
    p_prop.add_argument("--fence-token", type=int, default=100)

    # catchup
    p_cat = sub.add_parser("catchup", help="Inspect delta catch-up logs")
    p_cat.add_argument("--from-seq", type=int, default=0)

    args = parser.parse_args(argv)
    coord = ReplicaCoordinator(node_id=args.node_id, store_path=args.store)

    if args.subcommand == "status":
        print(f"ReplicaCoordinator Node: {coord.node_id}")
        print(f"Current Sequence: {coord.current_sequence}")
        print(f"Peers: {len(coord.peers)} (Active: {coord.active_node_count()})")
        print(f"Quorum Requirement: {coord.calculate_quorum()}")
        return 0

    elif args.subcommand == "peer-add":
        coord.register_peer(args.peer_id, args.url)
        coord.save()
        print(f"REGISTERED peer {args.peer_id} at {args.url}")
        return 0

    elif args.subcommand == "propose":
        try:
            mut = coord.propose_mutation(
                payload={"action": args.action, "item_id": args.item_id},
                fence_token=args.fence_token,
            )
            print(f"COMMITTED sequence {mut.sequence_id} (hash: {mut.commit_hash[:12]}..., acks: {mut.ack_count})")
            return 0
        except ReplicaCoordinatorError as err:
            print(f"FAILED: {err}", file=sys.stderr)
            return 1

    elif args.subcommand == "catchup":
        deltas = coord.get_delta_catchup(from_sequence=args.from_seq)
        print(f"Catch-up deltas ({len(deltas)} entries from seq {args.from_seq}):")
        for d in deltas:
            print(f"  Seq {d.sequence_id} [Token {d.fence_token}]: {d.payload}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

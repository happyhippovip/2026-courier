"""Worker Heartbeat Health Aggregator and Cluster Liveness Mesh.

Aggregates worker heartbeats, evaluates sliding window timeouts,
classifies silent nodes as DEAD, manages graceful node draining,
and computes cluster quorum health.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from enum import Enum
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional


class NodeHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DRAINING = "DRAINING"
    DEAD = "DEAD"


@dataclass
class NodeRecord:
    """Tracked heartbeat and state record for an individual cluster node."""

    node_id: str
    status: NodeHealthStatus
    last_heartbeat: float
    heartbeat_seq: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value if isinstance(self.status, NodeHealthStatus) else str(self.status),
            "last_heartbeat": self.last_heartbeat,
            "heartbeat_seq": self.heartbeat_seq,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeRecord:
        return cls(
            node_id=str(data["node_id"]),
            status=NodeHealthStatus(data.get("status", NodeHealthStatus.HEALTHY.value)),
            last_heartbeat=float(data.get("last_heartbeat", 0.0)),
            heartbeat_seq=int(data.get("heartbeat_seq", 0)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ClusterHealthSummary:
    """Cluster-wide aggregated liveness and quorum report."""

    total_nodes: int
    healthy_nodes: int
    degraded_nodes: int
    draining_nodes: int
    dead_nodes: int
    health_ratio: float
    quorum_achieved: bool
    evaluated_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClusterHealthMesh:
    """Coordinates node liveness evaluation, heartbeats, and cluster quorum."""

    def __init__(
        self,
        mesh_path: str | Path,
        heartbeat_timeout_seconds: float = 15.0,
        quorum_threshold: float = 0.5,
    ) -> None:
        self.mesh_path = Path(mesh_path)
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.quorum_threshold = quorum_threshold
        self._nodes: dict[str, NodeRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.mesh_path.exists():
            return
        try:
            with open(self.mesh_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._nodes = {
                k: NodeRecord.from_dict(v) for k, v in data.get("nodes", {}).items()
            }
        except Exception:
            self._nodes = {}

    def _save(self) -> None:
        self.mesh_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "updated_at": time.time(),
        }
        tmp_file = self.mesh_path.with_suffix(self.mesh_path.suffix + ".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp_file.replace(self.mesh_path)

    def record_heartbeat(
        self,
        node_id: str,
        status: NodeHealthStatus | str = NodeHealthStatus.HEALTHY,
        timestamp: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> NodeRecord:
        """Register or update node heartbeat."""
        now = timestamp if timestamp is not None else time.time()
        node_status = NodeHealthStatus(status) if not isinstance(status, NodeHealthStatus) else status

        record = self._nodes.get(node_id)
        if record is None:
            record = NodeRecord(
                node_id=node_id,
                status=node_status,
                last_heartbeat=now,
                heartbeat_seq=1,
                metadata=metadata or {},
            )
        else:
            record.heartbeat_seq += 1
            record.last_heartbeat = now
            if metadata:
                record.metadata.update(metadata)
            # If node was explicitly DRAINING, keep it unless new status is provided explicitly
            if record.status == NodeHealthStatus.DRAINING and status == NodeHealthStatus.HEALTHY:
                record.status = NodeHealthStatus.DRAINING
            else:
                record.status = node_status

        self._nodes[node_id] = record
        self._save()
        return record

    def get_node(self, node_id: str) -> Optional[NodeRecord]:
        return self._nodes.get(node_id)

    def drain_node(self, node_id: str) -> bool:
        """Initiate graceful draining on a node."""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.status = NodeHealthStatus.DRAINING
        self._save()
        return True

    def evaluate_cluster_health(self, now: Optional[float] = None) -> ClusterHealthSummary:
        """Evaluate sliding window timeouts and compute cluster quorum."""
        curr_time = now if now is not None else time.time()

        healthy = 0
        degraded = 0
        draining = 0
        dead = 0

        for node in self._nodes.values():
            elapsed = curr_time - node.last_heartbeat
            if elapsed > self.heartbeat_timeout_seconds:
                node.status = NodeHealthStatus.DEAD

            if node.status == NodeHealthStatus.HEALTHY:
                healthy += 1
            elif node.status == NodeHealthStatus.DEGRADED:
                degraded += 1
            elif node.status == NodeHealthStatus.DRAINING:
                draining += 1
            elif node.status == NodeHealthStatus.DEAD:
                dead += 1

        self._save()

        total = len(self._nodes)
        health_ratio = round(healthy / total, 4) if total > 0 else 1.0
        quorum_achieved = health_ratio >= self.quorum_threshold

        return ClusterHealthSummary(
            total_nodes=total,
            healthy_nodes=healthy,
            degraded_nodes=degraded,
            draining_nodes=draining,
            dead_nodes=dead,
            health_ratio=health_ratio,
            quorum_achieved=quorum_achieved,
            evaluated_at=curr_time,
        )

    def prune_dead_nodes(self, max_dead_age_seconds: float = 60.0, now: Optional[float] = None) -> list[str]:
        """Prune nodes in DEAD status older than threshold."""
        curr_time = now if now is not None else time.time()
        pruned = []

        for node_id, node in list(self._nodes.items()):
            if node.status == NodeHealthStatus.DEAD:
                if (curr_time - node.last_heartbeat) >= max_dead_age_seconds:
                    pruned.append(node_id)
                    del self._nodes[node_id]

        if pruned:
            self._save()

        return pruned


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker Heartbeat Health Aggregator & Liveness Mesh")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # heartbeat
    hb_p = subparsers.add_parser("heartbeat", help="Send worker heartbeat")
    hb_p.add_argument("--mesh", required=True, help="Path to mesh state file")
    hb_p.add_argument("--node", required=True, help="Node ID")
    hb_p.add_argument("--status", default="HEALTHY", choices=["HEALTHY", "DEGRADED", "DRAINING", "DEAD"])
    hb_p.add_argument("--metadata", default="{}", help="Metadata JSON string")

    # drain
    dr_p = subparsers.add_parser("drain", help="Drain a worker node")
    dr_p.add_argument("--mesh", required=True, help="Path to mesh state file")
    dr_p.add_argument("--node", required=True, help="Node ID to drain")

    # status
    st_p = subparsers.add_parser("status", help="Get cluster health and quorum status")
    st_p.add_argument("--mesh", required=True, help="Path to mesh state file")

    # prune
    pr_p = subparsers.add_parser("prune", help="Prune dead nodes")
    pr_p.add_argument("--mesh", required=True, help="Path to mesh state file")
    pr_p.add_argument("--age", type=float, default=60.0, help="Max dead age in seconds")

    args = parser.parse_args()
    mesh = ClusterHealthMesh(args.mesh)

    if args.action == "heartbeat":
        meta = json.loads(args.metadata)
        record = mesh.record_heartbeat(node_id=args.node, status=args.status, metadata=meta)
        print(f"Recorded heartbeat for {record.node_id} (seq={record.heartbeat_seq}, status={record.status.value})")

    elif args.action == "drain":
        success = mesh.drain_node(args.node)
        print(f"Drained node {args.node}: {success}")

    elif args.action == "status":
        summary = mesh.evaluate_cluster_health()
        print(json.dumps(summary.to_dict(), indent=2))

    elif args.action == "prune":
        pruned = mesh.prune_dead_nodes(max_dead_age_seconds=args.age)
        print(f"Pruned {len(pruned)} dead nodes: {', '.join(pruned) if pruned else 'none'}")


if __name__ == "__main__":
    main()

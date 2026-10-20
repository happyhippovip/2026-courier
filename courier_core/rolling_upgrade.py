"""Zero-Downtime Rolling Upgrade and Version Handshake Protocol for Courier Symphony.

Provides worker version handshake validation, schema capability negotiation,
phased rolling upgrade orchestration (drain, upgrade, verify, activate),
quorum breach prevention, and automated rollback upon canary failure.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


class NodeUpgradeState(str, Enum):
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    UPGRADING = "UPGRADING"
    VERIFYING = "VERIFYING"
    FAILED = "FAILED"


class HandshakeStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED_OUTDATED = "REJECTED_OUTDATED"
    REJECTED_UNSUPPORTED = "REJECTED_UNSUPPORTED"


class RollingUpgradeError(Exception):
    """Base exception for rolling upgrade protocol errors."""
    pass


class QuorumBreachRiskError(RollingUpgradeError):
    """Raised when draining or upgrading a node risks violating cluster quorum."""
    pass


class IncompatibleVersionError(RollingUpgradeError):
    """Raised when an incompatible worker version attempts cluster participation."""
    pass


@dataclass
class NodeVersionInfo:
    node_id: str
    version: str
    schema_version: int
    capabilities: List[str] = field(default_factory=list)


@dataclass
class HandshakeResponse:
    status: HandshakeStatus
    target_version: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "target_version": self.target_version,
            "message": self.message,
        }


@dataclass
class ClusterNodeRecord:
    node_id: str
    version: str
    schema_version: int
    previous_version: str = ""
    state: NodeUpgradeState = NodeUpgradeState.ACTIVE
    last_reason: str = "Registered"
    last_heartbeat: str = ""

    def __post_init__(self):
        if not self.last_heartbeat:
            self.last_heartbeat = datetime.now(timezone.utc).isoformat()
        if not self.previous_version:
            self.previous_version = self.version

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClusterNodeRecord:
        data_copy = dict(data)
        data_copy["state"] = NodeUpgradeState(data_copy["state"])
        return cls(**data_copy)


class RollingUpgradeCoordinator:
    """Orchestrates rolling node upgrades and validates cluster version compatibility."""

    def __init__(
        self,
        store_path: Optional[str] = None,
        min_schema_version: int = 2,
        max_schema_version: int = 4,
        target_version: str = "3.2.0",
        max_concurrent_upgrades: int = 1,
    ):
        self.store_path = store_path
        self.min_schema_version = min_schema_version
        self.max_schema_version = max_schema_version
        self.target_version = target_version
        self.max_concurrent_upgrades = max_concurrent_upgrades
        self.nodes: Dict[str, ClusterNodeRecord] = {}

        if self.store_path and Path(self.store_path).exists():
            self.load()

    def handshake(self, info: NodeVersionInfo) -> HandshakeResponse:
        """Validate node schema version against coordinator policy."""
        if info.schema_version < self.min_schema_version:
            return HandshakeResponse(
                status=HandshakeStatus.REJECTED_OUTDATED,
                target_version=self.target_version,
                message=f"Outdated schema version {info.schema_version} (minimum required is {self.min_schema_version})",
            )
        if info.schema_version > self.max_schema_version:
            return HandshakeResponse(
                status=HandshakeStatus.REJECTED_UNSUPPORTED,
                target_version=self.target_version,
                message=f"Unsupported future schema version {info.schema_version} (maximum supported is {self.max_schema_version})",
            )
        return HandshakeResponse(
            status=HandshakeStatus.ACCEPTED,
            target_version=self.target_version,
            message="Node version handshake accepted",
        )

    def register_node(self, node_id: str, version: str, schema_version: int) -> None:
        self.nodes[node_id] = ClusterNodeRecord(
            node_id=node_id,
            version=version,
            schema_version=schema_version,
            previous_version=version,
            state=NodeUpgradeState.ACTIVE,
        )

    def get_node_state(self, node_id: str) -> NodeUpgradeState:
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found in cluster registry")
        return self.nodes[node_id].state

    def begin_drain(self, node_id: str) -> None:
        """Initiate graceful drain phase, ensuring quorum is not breached."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found")

        non_active = sum(1 for n in self.nodes.values() if n.state != NodeUpgradeState.ACTIVE)
        if non_active >= self.max_concurrent_upgrades:
            raise QuorumBreachRiskError(
                f"Cannot drain node '{node_id}': max concurrent upgrades ({self.max_concurrent_upgrades}) already active"
            )

        self.nodes[node_id].state = NodeUpgradeState.DRAINING
        self.nodes[node_id].last_reason = "Initiated graceful drain for upgrade"
        if self.store_path:
            self.save()

    def begin_upgrade(self, node_id: str, target_version: str) -> None:
        """Transition node to UPGRADING phase and assign target binary version."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found")

        node = self.nodes[node_id]
        node.previous_version = node.version
        node.version = target_version
        node.state = NodeUpgradeState.UPGRADING
        node.last_reason = f"Upgrading binary to {target_version}"
        if self.store_path:
            self.save()

    def begin_verify(self, node_id: str) -> None:
        """Transition node to canary verification phase."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found")
        self.nodes[node_id].state = NodeUpgradeState.VERIFYING
        self.nodes[node_id].last_reason = "Running canary health and verification check"
        if self.store_path:
            self.save()

    def activate_node(self, node_id: str) -> None:
        """Mark node ACTIVE after successful upgrade and verification."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found")
        self.nodes[node_id].state = NodeUpgradeState.ACTIVE
        self.nodes[node_id].last_reason = f"Upgrade verified and node active at version {self.nodes[node_id].version}"
        if self.store_path:
            self.save()

    def rollback_node(self, node_id: str, reason: str = "") -> None:
        """Trigger automatic rollback restoring previous binary version."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found")
        node = self.nodes[node_id]
        node.version = node.previous_version
        node.state = NodeUpgradeState.ACTIVE
        node.last_reason = f"Automatic rollback to {node.version}: {reason}"
        if self.store_path:
            self.save()

    def save(self) -> None:
        if not self.store_path:
            return
        p = Path(self.store_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "target_version": self.target_version,
            "min_schema_version": self.min_schema_version,
            "max_schema_version": self.max_schema_version,
            "max_concurrent_upgrades": self.max_concurrent_upgrades,
            "nodes": {nid: rec.to_dict() for nid, rec in self.nodes.items()},
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path or not Path(self.store_path).exists():
            return
        raw = json.loads(Path(self.store_path).read_text(encoding="utf-8"))
        self.target_version = raw.get("target_version", self.target_version)
        self.min_schema_version = int(raw.get("min_schema_version", self.min_schema_version))
        self.max_schema_version = int(raw.get("max_schema_version", self.max_schema_version))
        self.max_concurrent_upgrades = int(raw.get("max_concurrent_upgrades", self.max_concurrent_upgrades))
        self.nodes = {
            nid: ClusterNodeRecord.from_dict(ndata)
            for nid, ndata in raw.get("nodes", {}).items()
        }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rolling Upgrade Coordinator CLI")
    parser.add_argument("--store", default="registries/rolling_upgrade.json", help="Path to state JSON")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # status
    sub.add_parser("status", help="Show cluster rolling upgrade status")

    # node-add
    p_add = sub.add_parser("node-add", help="Register cluster worker node")
    p_add.add_argument("--node-id", required=True)
    p_add.add_argument("--version", default="3.1.0")
    p_add.add_argument("--schema", type=int, default=3)

    # drain
    p_dr = sub.add_parser("drain", help="Initiate graceful node drain")
    p_dr.add_argument("--node-id", required=True)

    # upgrade
    p_up = sub.add_parser("upgrade", help="Begin node upgrade")
    p_up.add_argument("--node-id", required=True)
    p_up.add_argument("--target-version", default="3.2.0")

    # activate
    p_act = sub.add_parser("activate", help="Activate node after upgrade verification")
    p_act.add_argument("--node-id", required=True)

    args = parser.parse_args(argv)
    coord = RollingUpgradeCoordinator(store_path=args.store)

    if args.subcommand == "status":
        print("=== UPGRADE STATUS ===")
        print(f"Target Version: {coord.target_version}")
        print(f"Total Nodes: {len(coord.nodes)}")
        for nid, node in coord.nodes.items():
            print(f" - {nid}: {node.state.value} (v{node.version}, schema={node.schema_version}) [{node.last_reason}]")
        return 0

    elif args.subcommand == "node-add":
        coord.register_node(args.node_id, version=args.version, schema_version=args.schema)
        coord.save()
        print(f"REGISTERED node {args.node_id} (version {args.version})")
        return 0

    elif args.subcommand == "drain":
        try:
            coord.begin_drain(args.node_id)
            coord.save()
            print(f"DRAINING node {args.node_id}")
            return 0
        except RollingUpgradeError as err:
            print(f"FAILED: {err}", file=sys.stderr)
            return 1

    elif args.subcommand == "upgrade":
        coord.begin_upgrade(args.node_id, target_version=args.target_version)
        coord.save()
        print(f"UPGRADING node {args.node_id} to {args.target_version}")
        return 0

    elif args.subcommand == "activate":
        coord.activate_node(args.node_id)
        coord.save()
        print(f"ACTIVATED node {args.node_id}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

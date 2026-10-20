"""Provenance Trace and Audit Chain Graph Generator (P36)

Constructs, validates, and visualizes cryptographic audit trails across
A->B->C execution pipelines, verifying unbroken parent-child hash links,
cycle-freedom, and mandatory verifier checkpoints prior to terminal DONE state.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class NodeType(str, Enum):
    DISPATCH = "DISPATCH"
    WORKER_EXECUTION = "WORKER_EXECUTION"
    HANDOFF = "HANDOFF"
    ARTIFACT = "ARTIFACT"
    VERIFICATION = "VERIFICATION"
    DONE = "DONE"


class ProvenanceRelation(str, Enum):
    GENERATED = "GENERATED"
    DERIVED_FROM = "DERIVED_FROM"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    VERIFIED_BY = "VERIFIED_BY"


@dataclass
class ProvenanceNode:
    node_id: str
    node_type: NodeType
    actor: str
    hash_sha256: str
    parent_hashes: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.node_type, str):
            self.node_type = NodeType(self.node_type)
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "actor": self.actor,
            "hash_sha256": self.hash_sha256,
            "parent_hashes": list(self.parent_hashes),
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProvenanceNode:
        return cls(
            node_id=str(data.get("node_id", "")),
            node_type=NodeType(data.get("node_type", "DISPATCH")),
            actor=str(data.get("actor", "")),
            hash_sha256=str(data.get("hash_sha256", "")),
            parent_hashes=[str(h) for h in data.get("parent_hashes", [])],
            timestamp=data.get("timestamp"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProvenanceEdge:
    parent_id: str
    child_id: str
    relation: ProvenanceRelation

    def __post_init__(self) -> None:
        if isinstance(self.relation, str):
            self.relation = ProvenanceRelation(self.relation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "relation": self.relation.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProvenanceEdge:
        return cls(
            parent_id=str(data.get("parent_id", "")),
            child_id=str(data.get("child_id", "")),
            relation=ProvenanceRelation(data.get("relation", "GENERATED")),
        )


class ProvenanceGraph:
    """Directed Acyclic Graph (DAG) validating cryptographic chain-of-custody."""

    def __init__(self) -> None:
        self._nodes: Dict[str, ProvenanceNode] = {}
        self._edges: List[ProvenanceEdge] = []

    def add_node(self, node: ProvenanceNode) -> None:
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[ProvenanceNode]:
        return self._nodes.get(node_id)

    def add_edge(
        self,
        parent_id: str,
        child_id: str,
        relation: ProvenanceRelation = ProvenanceRelation.GENERATED,
    ) -> None:
        self._edges.append(
            ProvenanceEdge(parent_id=parent_id, child_id=child_id, relation=relation)
        )

    def verify_integrity(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Check parent & child existence
        for edge in self._edges:
            if edge.parent_id not in self._nodes:
                errors.append(f"Missing parent node '{edge.parent_id}' in edge")
            if edge.child_id not in self._nodes:
                errors.append(f"Missing child node '{edge.child_id}' in edge")

        if errors:
            return False, errors

        # 2. Cycle detection via DFS
        adj: Dict[str, List[str]] = collections.defaultdict(list)
        for edge in self._edges:
            adj[edge.parent_id].append(edge.child_id)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def _has_cycle(v: str) -> bool:
            visited.add(v)
            rec_stack.add(v)
            for neighbor in adj[v]:
                if neighbor not in visited:
                    if _has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(v)
            return False

        for node_id in self._nodes:
            if node_id not in visited:
                if _has_cycle(node_id):
                    errors.append(f"Cycle detected in provenance graph at node '{node_id}'")
                    break

        # 3. Hash-chaining verification
        for edge in self._edges:
            parent = self._nodes[edge.parent_id]
            child = self._nodes[edge.child_id]
            if not child.parent_hashes or parent.hash_sha256 not in child.parent_hashes:
                errors.append(
                    f"Hash chain mismatch between '{edge.parent_id}' and '{edge.child_id}': "
                    f"child does not reference parent hash '{parent.hash_sha256}'"
                )

        # 4. Mandatory Verifier check before DONE
        rev_adj: Dict[str, List[str]] = collections.defaultdict(list)
        for edge in self._edges:
            rev_adj[edge.child_id].append(edge.parent_id)

        done_nodes = [n for n in self._nodes.values() if n.node_type == NodeType.DONE]
        for done_node in done_nodes:
            queue = [done_node.node_id]
            seen: Set[str] = set()
            has_verification = False
            has_dispatch = False

            while queue:
                curr_id = queue.pop(0)
                if curr_id in seen:
                    continue
                seen.add(curr_id)

                curr_node = self._nodes[curr_id]
                if curr_node.node_type == NodeType.VERIFICATION:
                    has_verification = True
                if curr_node.node_type == NodeType.DISPATCH:
                    has_dispatch = True

                for parent_id in rev_adj[curr_id]:
                    queue.append(parent_id)

            if not has_verification:
                errors.append(
                    f"Verification step required before DONE for node '{done_node.node_id}'"
                )
            if not has_dispatch:
                errors.append(
                    f"Dispatch root required before DONE for node '{done_node.node_id}'"
                )

        return len(errors) == 0, errors

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self._nodes.values():
            safe_label = f"{node.node_type.value}: {node.actor} ({node.hash_sha256[:8]})"
            lines.append(f'    {node.node_id}["{safe_label}"]')

        for edge in self._edges:
            lines.append(f"    {edge.parent_id} -->|{edge.relation.value}| {edge.child_id}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProvenanceGraph:
        graph = cls()
        for n_data in data.get("nodes", []):
            graph.add_node(ProvenanceNode.from_dict(n_data))
        for e_data in data.get("edges", []):
            edge = ProvenanceEdge.from_dict(e_data)
            graph.add_edge(edge.parent_id, edge.child_id, edge.relation)
        return graph


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Provenance Graph CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ver_parser = subparsers.add_parser("verify", help="Verify integrity of provenance graph")
    ver_parser.add_argument("--graph", required=True, help="Path to graph JSON file")

    mer_parser = subparsers.add_parser("mermaid", help="Export graph to Mermaid diagram")
    mer_parser.add_argument("--graph", required=True, help="Path to graph JSON file")

    args = parser.parse_args(argv)
    data = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    graph = ProvenanceGraph.from_dict(data)

    if args.command == "verify":
        is_valid, errors = graph.verify_integrity()
        print(json.dumps({
            "valid": is_valid,
            "errors": errors,
            "node_count": len(graph._nodes),
            "edge_count": len(graph._edges),
        }, indent=2))
        return 0 if is_valid else 1

    elif args.command == "mermaid":
        print(graph.to_mermaid())
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

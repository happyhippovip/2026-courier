import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass(frozen=True)
class ProvenanceNode:
    node_id: str
    source_uri: str
    producer: str
    verifier: str
    timestamp: float
    environment: str
    parent_sha: Optional[str]
    payload_hash: str

    def calculate_sha(self) -> str:
        data = f"{self.node_id}|{self.source_uri}|{self.producer}|{self.verifier}|{self.timestamp}|{self.environment}|{self.parent_sha}|{self.payload_hash}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class ProvenanceGraph:
    """
    MAC-02: Track source, producer, verifier, timestamp, SHA, environment.
    """
    def __init__(self):
        self.nodes: Dict[str, ProvenanceNode] = {}

    def add_node(self, node: ProvenanceNode) -> str:
        if node.parent_sha and node.parent_sha not in self.nodes:
            raise ValueError(f"Parent SHA {node.parent_sha} not found in graph.")
        node_sha = node.calculate_sha()
        self.nodes[node_sha] = node
        return node_sha

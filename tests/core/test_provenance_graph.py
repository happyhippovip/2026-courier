import pytest
from courier_core.provenance_graph import ProvenanceGraph, ProvenanceNode
import time

def test_provenance_graph_linkage():
    graph = ProvenanceGraph()
    root = ProvenanceNode(
        "root-1", "local://root", "system", "system", time.time(), "mac", None, "hash1"
    )
    root_sha = graph.add_node(root)
    assert root_sha in graph.nodes

    child = ProvenanceNode(
        "child-1", "local://child", "worker-1", "verifier-1", time.time(), "mac", root_sha, "hash2"
    )
    child_sha = graph.add_node(child)
    assert child_sha in graph.nodes
    
    # Invalid parent
    invalid = ProvenanceNode(
        "child-2", "local://invalid", "worker-1", "verifier-1", time.time(), "mac", "unknown-sha", "hash3"
    )
    with pytest.raises(ValueError):
        graph.add_node(invalid)

import json
import pytest
from pathlib import Path
from courier_core.provenance_graph import (
    ProvenanceNode,
    ProvenanceGraph,
    ProvenanceRelation,
    NodeType,
)


def create_valid_pipeline_graph() -> ProvenanceGraph:
    graph = ProvenanceGraph()

    # 1. Dispatch
    h_dispatch = "hash-dispatch-001"
    graph.add_node(ProvenanceNode(
        node_id="step-1-dispatch",
        node_type=NodeType.DISPATCH,
        actor="dispatcher",
        hash_sha256=h_dispatch,
        parent_hashes=[],
    ))

    # 2. Worker A execution
    h_worker_a = "hash-worker-a-002"
    graph.add_node(ProvenanceNode(
        node_id="step-2-workerA",
        node_type=NodeType.WORKER_EXECUTION,
        actor="worker-a",
        hash_sha256=h_worker_a,
        parent_hashes=[h_dispatch],
    ))
    graph.add_edge("step-1-dispatch", "step-2-workerA", ProvenanceRelation.GENERATED)

    # 3. Handoff
    h_handoff = "hash-handoff-003"
    graph.add_node(ProvenanceNode(
        node_id="step-3-handoff",
        node_type=NodeType.HANDOFF,
        actor="worker-a",
        hash_sha256=h_handoff,
        parent_hashes=[h_worker_a],
    ))
    graph.add_edge("step-2-workerA", "step-3-handoff", ProvenanceRelation.TRANSFERRED_TO)

    # 4. Worker B execution
    h_worker_b = "hash-worker-b-004"
    graph.add_node(ProvenanceNode(
        node_id="step-4-workerB",
        node_type=NodeType.WORKER_EXECUTION,
        actor="worker-b",
        hash_sha256=h_worker_b,
        parent_hashes=[h_handoff],
    ))
    graph.add_edge("step-3-handoff", "step-4-workerB", ProvenanceRelation.DERIVED_FROM)

    # 5. Verifier
    h_verifier = "hash-verifier-005"
    graph.add_node(ProvenanceNode(
        node_id="step-5-verifier",
        node_type=NodeType.VERIFICATION,
        actor="verifier-node",
        hash_sha256=h_verifier,
        parent_hashes=[h_worker_b],
    ))
    graph.add_edge("step-4-workerB", "step-5-verifier", ProvenanceRelation.VERIFIED_BY)

    # 6. Terminal Done
    h_done = "hash-done-006"
    graph.add_node(ProvenanceNode(
        node_id="step-6-done",
        node_type=NodeType.DONE,
        actor="ledger-writer",
        hash_sha256=h_done,
        parent_hashes=[h_verifier],
    ))
    graph.add_edge("step-5-verifier", "step-6-done", ProvenanceRelation.GENERATED)

    return graph


def test_valid_linear_pipeline_provenance():
    graph = create_valid_pipeline_graph()
    is_valid, errors = graph.verify_integrity()
    assert is_valid is True
    assert errors == []


def test_detect_broken_parent_link():
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(
        node_id="child",
        node_type=NodeType.DONE,
        actor="actor",
        hash_sha256="h1",
    ))
    graph.add_edge("missing-parent", "child", ProvenanceRelation.GENERATED)

    is_valid, errors = graph.verify_integrity()
    assert is_valid is False
    assert any("missing-parent" in e for e in errors)


def test_detect_cycle_in_provenance():
    graph = ProvenanceGraph()
    graph.add_node(ProvenanceNode(node_id="A", node_type=NodeType.DISPATCH, actor="a", hash_sha256="ha"))
    graph.add_node(ProvenanceNode(node_id="B", node_type=NodeType.WORKER_EXECUTION, actor="b", hash_sha256="hb"))

    # Cycle A -> B -> A
    graph.add_edge("A", "B", ProvenanceRelation.GENERATED)
    graph.add_edge("B", "A", ProvenanceRelation.GENERATED)

    is_valid, errors = graph.verify_integrity()
    assert is_valid is False
    assert any("Cycle detected" in e for e in errors)


def test_detect_tampered_hash_chain():
    graph = create_valid_pipeline_graph()
    # Tamper with child's parent_hashes
    graph.get_node("step-4-workerB").parent_hashes = ["tampered-hash-000"]

    is_valid, errors = graph.verify_integrity()
    assert is_valid is False
    assert any("Hash chain mismatch" in e for e in errors)

    # Omitting parent_hashes ([]) on a child node must also fail hash chain verification
    graph2 = create_valid_pipeline_graph()
    graph2.get_node("step-4-workerB").parent_hashes = []
    is_valid2, errors2 = graph2.verify_integrity()
    assert is_valid2 is False
    assert any("Hash chain mismatch" in e for e in errors2)


def test_verify_done_without_verifier_fails():
    graph = ProvenanceGraph()
    # Dispatch -> Worker -> Done (skipping Verifier)
    graph.add_node(ProvenanceNode(node_id="d", node_type=NodeType.DISPATCH, actor="d", hash_sha256="hd"))
    graph.add_node(ProvenanceNode(node_id="w", node_type=NodeType.WORKER_EXECUTION, actor="w", hash_sha256="hw", parent_hashes=["hd"]))
    graph.add_node(ProvenanceNode(node_id="done", node_type=NodeType.DONE, actor="dw", hash_sha256="hdone", parent_hashes=["hw"]))

    graph.add_edge("d", "w", ProvenanceRelation.GENERATED)
    graph.add_edge("w", "done", ProvenanceRelation.GENERATED)

    is_valid, errors = graph.verify_integrity()
    assert is_valid is False
    assert any("Verification step required before DONE" in e for e in errors)


def test_export_mermaid_diagram():
    graph = create_valid_pipeline_graph()
    mermaid = graph.to_mermaid()

    assert "graph TD" in mermaid
    assert "step-1-dispatch" in mermaid
    assert "step-6-done" in mermaid
    assert "VERIFIED_BY" in mermaid


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    graph = create_valid_pipeline_graph()
    graph_file = tmp_path / "provenance.json"
    graph_file.write_text(json.dumps(graph.to_dict(), indent=2), encoding="utf-8")

    # Verify via CLI
    cmd_verify = [
        sys.executable,
        "-m",
        "courier_core.provenance_graph",
        "verify",
        "--graph",
        str(graph_file),
    ]
    proc_verify = subprocess.run(cmd_verify, capture_output=True, text=True, check=True)
    out_verify = json.loads(proc_verify.stdout)
    assert out_verify["valid"] is True
    assert out_verify["errors"] == []

    # Export mermaid via CLI
    cmd_mermaid = [
        sys.executable,
        "-m",
        "courier_core.provenance_graph",
        "mermaid",
        "--graph",
        str(graph_file),
    ]
    proc_mermaid = subprocess.run(cmd_mermaid, capture_output=True, text=True, check=True)
    assert "graph TD" in proc_mermaid.stdout

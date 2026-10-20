"""Tests for courier_core.cluster_health_mesh - Worker Heartbeat Health Aggregator & Cluster Liveness Mesh."""

from __future__ import annotations

import json
import pytest

from courier_core.cluster_health_mesh import (
    NodeHealthStatus,
    NodeRecord,
    ClusterHealthMesh,
    ClusterHealthSummary,
    main,
)


def test_record_heartbeat_and_sequence_monotonicity(tmp_path):
    mesh_path = tmp_path / "mesh.json"
    mesh = ClusterHealthMesh(mesh_path, heartbeat_timeout_seconds=5.0)

    n1 = mesh.record_heartbeat(node_id="worker-win-1", status=NodeHealthStatus.HEALTHY, metadata={"cpu": 25.0})
    assert n1.node_id == "worker-win-1"
    assert n1.heartbeat_seq == 1
    assert n1.status == NodeHealthStatus.HEALTHY
    assert n1.metadata["cpu"] == 25.0

    n2 = mesh.record_heartbeat(node_id="worker-win-1", status=NodeHealthStatus.HEALTHY, metadata={"cpu": 30.0})
    assert n2.heartbeat_seq == 2


def test_sliding_window_timeout_classifies_dead_nodes(tmp_path):
    mesh_path = tmp_path / "mesh.json"
    mesh = ClusterHealthMesh(mesh_path, heartbeat_timeout_seconds=10.0)

    t0 = 1000.0
    mesh.record_heartbeat("worker-active", status=NodeHealthStatus.HEALTHY, timestamp=t0)
    mesh.record_heartbeat("worker-silent", status=NodeHealthStatus.HEALTHY, timestamp=t0)

    # Active sends heartbeat at t0 + 5s
    mesh.record_heartbeat("worker-active", status=NodeHealthStatus.HEALTHY, timestamp=t0 + 5.0)

    # Evaluate at t0 + 15s: worker-silent has elapsed 15s (> 10s timeout) -> DEAD
    # worker-active has elapsed 10s (<= 10s timeout) -> HEALTHY
    summary = mesh.evaluate_cluster_health(now=t0 + 15.0)
    assert summary.total_nodes == 2
    assert summary.healthy_nodes == 1
    assert summary.dead_nodes == 1
    assert summary.quorum_achieved is True  # 1/2 is 50% >= quorum


def test_node_drainage_lifecycle(tmp_path):
    mesh_path = tmp_path / "mesh.json"
    mesh = ClusterHealthMesh(mesh_path, heartbeat_timeout_seconds=10.0)

    mesh.record_heartbeat("worker-to-drain", status=NodeHealthStatus.HEALTHY)
    assert mesh.get_node("worker-to-drain").status == NodeHealthStatus.HEALTHY

    # Drain node
    mesh.drain_node("worker-to-drain")
    assert mesh.get_node("worker-to-drain").status == NodeHealthStatus.DRAINING

    summary = mesh.evaluate_cluster_health()
    assert summary.draining_nodes == 1


def test_prune_dead_nodes(tmp_path):
    mesh_path = tmp_path / "mesh.json"
    mesh = ClusterHealthMesh(mesh_path, heartbeat_timeout_seconds=5.0)

    t0 = 2000.0
    mesh.record_heartbeat("node-1", timestamp=t0)
    mesh.record_heartbeat("node-2", timestamp=t0)

    # Evaluate at t0 + 10s -> both dead
    mesh.evaluate_cluster_health(now=t0 + 10.0)
    assert mesh.get_node("node-1").status == NodeHealthStatus.DEAD

    # Prune nodes older than 8s
    pruned = mesh.prune_dead_nodes(max_dead_age_seconds=8.0, now=t0 + 10.0)
    assert "node-1" in pruned
    assert "node-2" in pruned
    assert mesh.get_node("node-1") is None


def test_quorum_calculation_and_health_ratio(tmp_path):
    mesh_path = tmp_path / "mesh.json"
    mesh = ClusterHealthMesh(mesh_path, heartbeat_timeout_seconds=5.0, quorum_threshold=0.6)

    t0 = 3000.0
    mesh.record_heartbeat("n1", timestamp=t0)
    mesh.record_heartbeat("n2", timestamp=t0)
    mesh.record_heartbeat("n3", timestamp=t0)

    # All 3 healthy -> ratio 1.0 >= 0.6 quorum
    s1 = mesh.evaluate_cluster_health(now=t0)
    assert s1.health_ratio == 1.0
    assert s1.quorum_achieved is True

    # 2 nodes go silent
    mesh.record_heartbeat("n1", timestamp=t0 + 10.0)
    s2 = mesh.evaluate_cluster_health(now=t0 + 10.0)
    assert s2.healthy_nodes == 1
    assert s2.dead_nodes == 2
    assert s2.health_ratio < 0.6
    assert s2.quorum_achieved is False


def test_cli_cluster_health_mesh(tmp_path, monkeypatch, capsys):
    mesh_file = tmp_path / "mesh.json"

    # Heartbeat
    monkeypatch.setattr(
        "sys.argv",
        [
            "cluster_health_mesh.py",
            "heartbeat",
            "--mesh",
            str(mesh_file),
            "--node",
            "win-worker-cli",
            "--status",
            "HEALTHY",
        ],
    )
    main()
    capsys.readouterr()  # Clear stdout buffer

    # Status
    monkeypatch.setattr(
        "sys.argv",
        [
            "cluster_health_mesh.py",
            "status",
            "--mesh",
            str(mesh_file),
        ],
    )
    main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["total_nodes"] == 1
    assert data["healthy_nodes"] == 1
    assert data["quorum_achieved"] is True

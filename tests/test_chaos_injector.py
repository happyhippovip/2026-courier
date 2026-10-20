"""Tests for courier_core.chaos_injector (End-to-End Cluster Chaos Injector)."""

import json
import pytest
from courier_core.chaos_injector import (
    ClusterChaosInjector,
    FaultType,
    FaultConfig,
    ChaosRunReport,
    NetworkPartitionFault,
    StaleTokenFault,
    PayloadCorruptionFault,
    LatencySpikeFault,
    main,
)
from courier_core.replica_coordinator import ReplicaCoordinator, QuorumUnavailableError
from courier_core.fencing_token import FencingTokenManager, StaleFencingTokenError
from courier_core.backpressure_controller import BackpressureController, FlowState


def test_network_partition_fault_injection_and_quorum_safety(tmp_path):
    coord = ReplicaCoordinator(node_id="leader-0", store_path=str(tmp_path / "rep.json"))
    coord.register_peer("peer-1", "http://10.0.0.1:8000")
    coord.register_peer("peer-2", "http://10.0.0.2:8000")

    injector = ClusterChaosInjector()
    fault = NetworkPartitionFault(partitioned_peers=["peer-1", "peer-2"])

    # Before fault: active node count = 3 >= quorum 2
    assert coord.active_node_count() == 3

    # Inject partition
    injector.inject_fault(fault, target=coord)
    assert coord.active_node_count() == 1

    # While partitioned, proposal must fail closed
    with pytest.raises(QuorumUnavailableError):
        coord.propose_mutation(payload={"data": "isolated_write"}, fence_token=100)

    # Heal partition
    injector.heal_fault(fault, target=coord)
    assert coord.active_node_count() == 3

    # After healing, mutations succeed
    commit = coord.propose_mutation(payload={"data": "healed_write"}, fence_token=101)
    assert commit.committed is True


def test_stale_token_split_brain_fault_injection(tmp_path):
    ft_store = tmp_path / "fences.json"
    fence_mgr = FencingTokenManager(state_path=ft_store)

    # Allocate initial lease with token generation 1
    t1 = fence_mgr.acquire("resource-alpha", "worker-1", ttl_seconds=60)
    assert t1.generation == 1
    fence_mgr.validate_and_commit("resource-alpha", t1.generation)

    # Allocate subsequent lease with token generation 2
    t2 = fence_mgr.acquire("resource-alpha", "worker-1", ttl_seconds=60)
    assert t2.generation == 2
    fence_mgr.validate_and_commit("resource-alpha", t2.generation)

    # Inject stale token split-brain fault using token 1
    injector = ClusterChaosInjector()
    stale_fault = StaleTokenFault(resource="resource-alpha", stale_token=t1.generation)

    outcome = injector.run_stale_token_check(fence_mgr, stale_fault)
    assert outcome["caught_expected_error"] is True
    assert outcome["invariant_held"] is True


def test_byzantine_payload_corruption_fault(tmp_path):
    injector = ClusterChaosInjector()
    fault = PayloadCorruptionFault(flip_bytes=True)

    original_payload = {"command": "deploy_service", "sha": "abcdef123456"}
    corrupted = fault.corrupt(original_payload)

    assert corrupted != original_payload
    assert corrupted["sha"] != original_payload["sha"]
    assert injector.verify_checksum(original_payload, corrupted) is False


def test_latency_spike_fault_and_backpressure_response(tmp_path):
    bp = BackpressureController(initial_rate=20.0)
    injector = ClusterChaosInjector()

    fault = LatencySpikeFault(spike_duration_ms=2500.0)
    injector.simulate_latency_feedback(bp, fault)

    # Rate should have decreased multiplicatively
    assert bp.current_rate < 20.0
    assert bp.state in (FlowState.THROTTLED, FlowState.SHED_LOAD)


def test_chaos_run_report_and_invariant_verification(tmp_path):
    injector = ClusterChaosInjector(report_path=str(tmp_path / "chaos_report.json"))

    report = injector.run_suite(
        faults=[
            NetworkPartitionFault(partitioned_peers=["node-b"]),
            StaleTokenFault(resource="res-test", stale_token=1),
            PayloadCorruptionFault(),
        ]
    )

    assert isinstance(report, ChaosRunReport)
    assert report.total_faults_injected == 3
    assert report.invariants_verified is True
    assert report.passed is True
    assert len(report.fault_outcomes) == 3


def test_cli_chaos_injector(tmp_path, capsys):
    report_file = tmp_path / "cli_chaos.json"

    # List faults CLI
    rc1 = main(["list-faults"])
    assert rc1 == 0
    assert "NETWORK_PARTITION" in capsys.readouterr().out

    # Run chaos suite CLI
    rc2 = main(["--report", str(report_file), "run", "--all"])
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "CHAOS SUITE: PASSED" in out
    assert report_file.exists()

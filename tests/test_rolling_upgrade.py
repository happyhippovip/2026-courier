"""Tests for courier_core.rolling_upgrade (Zero-Downtime Rolling Upgrade Protocol)."""

import json
import pytest
from courier_core.rolling_upgrade import (
    RollingUpgradeCoordinator,
    NodeVersionInfo,
    NodeUpgradeState,
    HandshakeStatus,
    QuorumBreachRiskError,
    IncompatibleVersionError,
    main,
)


def test_version_handshake_compatibility_and_rejection():
    coord = RollingUpgradeCoordinator(
        min_schema_version=2,
        max_schema_version=4,
        target_version="3.2.0",
    )

    # Compatible worker v3.1.0 with schema 3
    node_a = NodeVersionInfo(
        node_id="worker-win-1",
        version="3.1.0",
        schema_version=3,
        capabilities=["fencing", "backpressure"],
    )
    res_a = coord.handshake(node_a)
    assert res_a.status == HandshakeStatus.ACCEPTED

    # Outdated worker v1.0.0 with schema 1
    node_b = NodeVersionInfo(
        node_id="worker-legacy",
        version="1.0.0",
        schema_version=1,
    )
    res_b = coord.handshake(node_b)
    assert res_b.status == HandshakeStatus.REJECTED_OUTDATED
    assert "outdated" in res_b.message.lower()

    # Incompatible futuristic worker schema 9
    node_c = NodeVersionInfo(
        node_id="worker-future",
        version="9.0.0",
        schema_version=9,
    )
    res_c = coord.handshake(node_c)
    assert res_c.status == HandshakeStatus.REJECTED_UNSUPPORTED


def test_four_phase_upgrade_lifecycle(tmp_path):
    coord = RollingUpgradeCoordinator(
        store_path=str(tmp_path / "upgrade.json"),
        target_version="3.2.0",
    )
    # Register 3 nodes
    coord.register_node("win-1", version="3.1.0", schema_version=3)
    coord.register_node("linux-1", version="3.1.0", schema_version=3)
    coord.register_node("mac-1", version="3.1.0", schema_version=3)

    assert coord.get_node_state("win-1") == NodeUpgradeState.ACTIVE

    # Phase 1: Drain
    coord.begin_drain("win-1")
    assert coord.get_node_state("win-1") == NodeUpgradeState.DRAINING

    # Phase 2: Upgrade
    coord.begin_upgrade("win-1", target_version="3.2.0")
    assert coord.get_node_state("win-1") == NodeUpgradeState.UPGRADING

    # Phase 3: Verify Canary
    coord.begin_verify("win-1")
    assert coord.get_node_state("win-1") == NodeUpgradeState.VERIFYING

    # Phase 4: Activate
    coord.activate_node("win-1")
    assert coord.get_node_state("win-1") == NodeUpgradeState.ACTIVE
    assert coord.nodes["win-1"].version == "3.2.0"


def test_quorum_safety_prevents_concurrent_excess_upgrades(tmp_path):
    coord = RollingUpgradeCoordinator(
        store_path=str(tmp_path / "upgrade.json"),
        max_concurrent_upgrades=1,
    )
    coord.register_node("win-1", version="3.1.0", schema_version=3)
    coord.register_node("linux-1", version="3.1.0", schema_version=3)
    coord.register_node("mac-1", version="3.1.0", schema_version=3)

    # Start upgrading win-1
    coord.begin_drain("win-1")
    assert coord.get_node_state("win-1") == NodeUpgradeState.DRAINING

    # Attempting to drain linux-1 while win-1 is not active must raise QuorumBreachRiskError
    with pytest.raises(QuorumBreachRiskError):
        coord.begin_drain("linux-1")


def test_automatic_rollback_on_canary_failure(tmp_path):
    coord = RollingUpgradeCoordinator(store_path=str(tmp_path / "upgrade.json"))
    coord.register_node("linux-1", version="3.1.0", schema_version=3)

    coord.begin_drain("linux-1")
    coord.begin_upgrade("linux-1", target_version="3.2.0-broken")
    coord.begin_verify("linux-1")

    # Verification fails -> triggers rollback
    coord.rollback_node("linux-1", reason="Canary self-test failed with exit code 1")

    assert coord.get_node_state("linux-1") == NodeUpgradeState.ACTIVE
    assert coord.nodes["linux-1"].version == "3.1.0"
    assert "rollback" in coord.nodes["linux-1"].last_reason.lower()


def test_persistence_and_upgrade_journal(tmp_path):
    store_file = tmp_path / "persisted_upgrade.json"
    c1 = RollingUpgradeCoordinator(store_path=str(store_file), target_version="3.5.0")
    c1.register_node("node-1", version="3.4.0", schema_version=3)
    c1.begin_drain("node-1")
    c1.save()

    # Reopen
    c2 = RollingUpgradeCoordinator(store_path=str(store_file))
    assert c2.target_version == "3.5.0"
    assert c2.get_node_state("node-1") == NodeUpgradeState.DRAINING


def test_cli_rolling_upgrade(tmp_path, capsys):
    state_file = tmp_path / "cli_upgrade.json"

    # Status CLI
    rc1 = main(["--store", str(state_file), "status"])
    assert rc1 == 0
    assert "UPGRADE STATUS" in capsys.readouterr().out

    # Register node CLI
    rc2 = main(["--store", str(state_file), "node-add", "--node-id", "win-box", "--version", "3.1.0", "--schema", "3"])
    assert rc2 == 0
    assert "REGISTERED" in capsys.readouterr().out

    # Drain node CLI
    rc3 = main(["--store", str(state_file), "drain", "--node-id", "win-box"])
    assert rc3 == 0
    assert "DRAINING" in capsys.readouterr().out

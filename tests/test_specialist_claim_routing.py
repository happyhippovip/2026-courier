from pathlib import Path
import pytest
from scripts.agent_warehouse import AgentCatalog, CapabilitySelector


def test_specialist_agents_implemented_and_routable():
    repo_root = Path(__file__).resolve().parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"

    catalog = AgentCatalog.load(catalog_path)
    selector = CapabilitySelector(catalog)

    # 1. Verify agent-asset-validator
    asset_val = next((a for a in catalog.agents if a.id == "agent-asset-validator"), None)
    assert asset_val is not None
    assert asset_val.status == "implemented"
    assert "asset_validation" in asset_val.capabilities
    for rel_path in asset_val.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist"

    # Route task
    exp_asset = selector.select_agent_for_task("asset_validation")
    assert exp_asset.selected_agent_id == "agent-asset-validator"
    assert "asset_validation" in exp_asset.capable_reason

    # 2. Verify agent-thought-curator
    thought_cur = next((a for a in catalog.agents if a.id == "agent-thought-curator"), None)
    assert thought_cur is not None
    assert thought_cur.status == "implemented"
    assert "thought_curation" in thought_cur.capabilities
    for rel_path in thought_cur.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist"

    # Route task
    exp_thought = selector.select_agent_for_task("thought_curation")
    assert exp_thought.selected_agent_id == "agent-thought-curator"
    assert "thought_curation" in exp_thought.capable_reason


def test_core_and_provider_agents_routable():
    repo_root = Path(__file__).resolve().parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"

    catalog = AgentCatalog.load(catalog_path)
    selector = CapabilitySelector(catalog)

    # 1. Chief Commander (orchestration, review)
    chief = next((a for a in catalog.agents if a.id == "agent-chief-commander"), None)
    assert chief is not None and chief.status == "implemented"
    assert "orchestration" in chief.capabilities
    for rel_path in chief.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist"

    exp_chief = selector.select_agent_for_task("orchestration")
    assert exp_chief.selected_agent_id == "agent-chief-commander"

    # 2. Antigravity Bridge (provider_execution, structured_result)
    agy = next((a for a in catalog.agents if a.id == "agent-antigravity-bridge"), None)
    assert agy is not None and agy.status == "implemented"
    assert "provider_execution" in agy.capabilities
    for rel_path in agy.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist"

    exp_agy = selector.select_agent_for_task("provider_execution")
    assert exp_agy.selected_agent_id in ("agent-antigravity-bridge", "agent-codex-bridge")

    # 3. Bodyguard Reserve Pool (temporary_role_assignment, capability_checked_reserve)
    bg = next((a for a in catalog.agents if a.id == "agent-bodyguard-alpha..hotel"), None)
    assert bg is not None and bg.status == "implemented"
    assert "temporary_role_assignment" in bg.capabilities
    for rel_path in bg.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist"

    exp_bg = selector.select_agent_for_task("temporary_role_assignment")
    assert exp_bg.selected_agent_id == "agent-bodyguard-alpha..hotel"


def test_single_writer_conflict_exclusion_and_implemented_filtering():
    repo_root = Path(__file__).resolve().parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"

    catalog = AgentCatalog.load(catalog_path)
    selector = CapabilitySelector(catalog)

    # 1. Active owner conflict: if agent-asset-validator is currently an active owner,
    # it must be excluded to prevent duplicate writers
    with pytest.raises(ValueError, match="No agent found for capability asset_validation"):
        selector.select_agent_for_task("asset_validation", current_owners=["agent-asset-validator"])

    # 2. Implementation filter:
    # 'watchdog' is owned by agent-snitch (status: partial)
    # With require_implemented=True (default), it must fail closed
    with pytest.raises(ValueError, match="No agent found for capability watchdog"):
        selector.select_agent_for_task("watchdog", require_implemented=True)

    # With require_implemented=False, it is selected as an exploratory/partial candidate
    exp_snitch = selector.select_agent_for_task("watchdog", require_implemented=False)
    assert exp_snitch.selected_agent_id == "agent-snitch"


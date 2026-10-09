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

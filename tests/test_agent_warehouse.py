import pytest
from pathlib import Path
from scripts.agent_warehouse import AgentCatalog, AgentCatalogEntry, CapabilitySelector


def _agent(agent_id, cost_class, capability="completion"):
    return AgentCatalogEntry(
        id=agent_id,
        display_name=agent_id,
        agent_class="core",
        status="implemented",
        owner_files=[],
        capabilities=[capability],
        write_authority=False,
        read_only_default=True,
        supported_hosts=[],
        provider_binding=None,
        cost_class=cost_class,
        heavy_job_class=None,
    )

def test_load_agent_catalog():
    repo_root = Path(__file__).parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"
    
    catalog = AgentCatalog.load(catalog_path)
    
    assert catalog.schema_version == "0.1-bootstrap"
    assert len(catalog.agents) > 0
    
    # Verify Chief Commander exists
    chief = next((a for a in catalog.agents if a.id == "agent-chief-commander"), None)
    assert chief is not None
    assert "orchestration" in chief.capabilities
    assert chief.cost_class == "local_or_routed"
    
    # Verify we can find a bodyguard
    bodyguard = next((a for a in catalog.agents if a.agent_class == "reserve" and "bodyguard" in a.id.lower()), None)
    if bodyguard:
        assert bodyguard.status == "planned" or bodyguard.status == "implemented"

def test_capability_selector():
    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)
    
    # Orchestration might only have one provider
    explanation = selector.select_agent_for_task("orchestration")
    assert explanation.selected_agent_id == "agent-chief-commander"
    assert "orchestration" in explanation.capable_reason
    
    # Check a more common capability if present, else just make sure logic holds
    try:
        exp_comp = selector.select_agent_for_task("completion")
        assert exp_comp.selected_agent_id is not None
    except ValueError:
        pass


def test_local_cost_class_is_planned_ahead_of_high():
    catalog = AgentCatalog("test", "test", [], [
        _agent("agent-high", "high"),
        _agent("agent-local", "local"),
    ])
    explanation = CapabilitySelector(catalog).select_agent_for_task("completion")
    assert explanation.selected_agent_id == "agent-local"
    assert explanation.planned_cost_class == "local"
    again = CapabilitySelector(catalog).select_agent_for_task("completion")
    assert again.planned_cost_class == explanation.planned_cost_class


def test_unranked_cost_class_is_not_called_cheapest():
    catalog = AgentCatalog("test", "test", [], [
        _agent("agent-high", "high"),
        _agent("agent-unknown", "unknown"),
    ])
    explanation = CapabilitySelector(catalog).select_agent_for_task("completion")
    assert explanation.selected_agent_id == "agent-high"
    assert explanation.planned_cost_class == "high"
    assert "not a cheapest-cost selection" in explanation.cost_reason


def test_unimplemented_agents_not_selected_by_default():
    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)

    with pytest.raises(ValueError, match="No agent found for capability.*routing_candidate"):
        selector.select_agent_for_task("routing_candidate")

    found = selector.select_agent_for_task("routing_candidate", require_implemented=False)
    assert found.selected_agent_id == "smart-resource-router"

    reloaded = CapabilitySelector(AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"))
    with pytest.raises(ValueError, match="No agent found for capability.*routing_candidate"):
        reloaded.select_agent_for_task("routing_candidate")

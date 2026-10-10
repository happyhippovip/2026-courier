import pytest
from pathlib import Path
from scripts.agent_warehouse import AgentCatalog, CapabilitySelector

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


def test_unimplemented_agents_not_selected_by_default():
    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)
    
    # routing_candidate is only registered by smart-resource-router which has status 'partial'
    with pytest.raises(ValueError, match="No agent found for capability routing_candidate"):
        selector.select_agent_for_task("routing_candidate")
        
    # When explicitly allowing non-implemented for inventory discovery, it can be found
    exp = selector.select_agent_for_task("routing_candidate", require_implemented=False)
    assert exp.selected_agent_id == "smart-resource-router"


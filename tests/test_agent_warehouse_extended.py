import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from scripts.agent_warehouse import (
    AgentCatalog,
    AgentCatalogEntry,
    CapabilitySelector,
    RoutingExplanation,
)


def test_agent_catalog_load_real_file():
    catalog_path = Path("docs/agent-warehouse/AGENT_CATALOG.json")
    assert catalog_path.exists()

    catalog = AgentCatalog.load(catalog_path)
    assert catalog.schema_version == "0.1-bootstrap"
    assert catalog.authority == "inventory_only_not_runtime_authority"
    assert len(catalog.agents) > 0

    chief = next((a for a in catalog.agents if a.id == "agent-chief-commander"), None)
    assert chief is not None
    assert chief.display_name == "Chief Commander"
    assert chief.agent_class == "core"
    assert "orchestration" in chief.capabilities


def test_capability_selector_chief_orchestration():
    catalog = AgentCatalog.load(Path("docs/agent-warehouse/AGENT_CATALOG.json"))
    selector = CapabilitySelector(catalog)

    explanation = selector.select_agent_for_task("orchestration")
    assert isinstance(explanation, RoutingExplanation)
    assert explanation.selected_agent_id == "agent-chief-commander"
    assert "orchestration" in explanation.capable_reason


def test_capability_selector_missing_capability_raises():
    catalog = AgentCatalog.load(Path("docs/agent-warehouse/AGENT_CATALOG.json"))
    selector = CapabilitySelector(catalog)

    with pytest.raises(ValueError, match="No agent found for capability"):
        selector.select_agent_for_task("nonexistent_teleportation_capability")


def test_capability_selector_ranking_and_fallback():
    agents = [
        AgentCatalogEntry(
            id="agent-expensive",
            display_name="Expensive Specialist",
            agent_class="specialist",
            status="active",
            owner_files=[],
            capabilities=["analysis"],
            write_authority=False,
            read_only_default=True,
            supported_hosts=["darwin", "linux"],
            provider_binding=None,
            cost_class="high",
            heavy_job_class=None,
        ),
        AgentCatalogEntry(
            id="agent-cheap",
            display_name="Cheap Core",
            agent_class="core",
            status="active",
            owner_files=[],
            capabilities=["analysis"],
            write_authority=False,
            read_only_default=True,
            supported_hosts=["darwin", "linux"],
            provider_binding=None,
            cost_class="free",
            heavy_job_class=None,
        ),
    ]
    catalog = AgentCatalog(
        schema_version="1.0",
        authority="test",
        related_issues=[],
        agents=agents,
    )
    selector = CapabilitySelector(catalog)

    # Core + Free must be preferred over Specialist + High
    exp = selector.select_agent_for_task("analysis")
    assert exp.selected_agent_id == "agent-cheap"
    assert exp.fallback_agent_id == "agent-expensive"


def test_capability_selector_host_filtering():
    agents = [
        AgentCatalogEntry(
            id="agent-win-only",
            display_name="Windows Worker",
            agent_class="specialist",
            status="active",
            owner_files=[],
            capabilities=["compile"],
            write_authority=False,
            read_only_default=True,
            supported_hosts=["win32"],
            provider_binding=None,
            cost_class="free",
            heavy_job_class=None,
        ),
        AgentCatalogEntry(
            id="agent-mac-only",
            display_name="Mac Worker",
            agent_class="specialist",
            status="active",
            owner_files=[],
            capabilities=["compile"],
            write_authority=False,
            read_only_default=True,
            supported_hosts=["darwin"],
            provider_binding=None,
            cost_class="free",
            heavy_job_class=None,
        ),
    ]
    catalog = AgentCatalog("1.0", "test", [], agents)
    selector = CapabilitySelector(catalog)

    exp_mac = selector.select_agent_for_task("compile", required_host="darwin")
    assert exp_mac.selected_agent_id == "agent-mac-only"

    exp_win = selector.select_agent_for_task("compile", required_host="win32")
    assert exp_win.selected_agent_id == "agent-win-only"

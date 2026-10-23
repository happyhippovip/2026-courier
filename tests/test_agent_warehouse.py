import json

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


def test_catalog_does_not_follow_a_symlink(tmp_path):
    secret = {
        "schema_version": "0.1-bootstrap",
        "agents": [{
            "id": "SECRET-AGENT",
            "display_name": "Secret",
            "class": "core",
            "status": "implemented",
        }],
    }
    outside = tmp_path / "outside-catalog.json"
    outside.write_text(json.dumps(secret), encoding="utf-8")
    linked = tmp_path / "catalog.json"
    linked.symlink_to(outside)

    def run(path):
        try:
            catalog = AgentCatalog.load(path)
            return None, [agent.id for agent in catalog.agents]
        except ValueError as exc:
            return str(exc), []

    file_err, file_ids = run(linked)
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "catalog.json").write_text(json.dumps(secret), encoding="utf-8")
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    parent = tmp_path / "linked-dir"
    parent.symlink_to(parent_outside)
    parent_err, parent_ids = run(parent / "catalog.json")
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (file_err, file_ids, parent_err, parent_ids, names) == (
        "refusing to follow a symlink",
        [],
        "refusing to follow a symlink",
        [],
        ["catalog.json", "keep.txt"],
    )

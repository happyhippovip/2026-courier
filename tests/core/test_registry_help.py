from courier_core.delta_capability_registry import SemanticDeltaRegistry, UpdateDelta
from courier_core.help_updates_backend import HelpBackendContract, UpdateState

def test_semantic_delta_registry():
    registry = SemanticDeltaRegistry()
    registry.register_update(UpdateDelta("v1", {"network", "disk"}, set()))
    
    assert "network" in registry.get_current_capabilities()
    
    registry.register_update(UpdateDelta("v2", {"cloud"}, {"disk"}))
    
    caps = registry.get_current_capabilities()
    assert "cloud" in caps
    assert "network" in caps
    assert "disk" not in caps
    
    # Query history
    disk_history = registry.query_update_history("disk")
    assert disk_history == ["v1", "v2"]
    
    cloud_history = registry.query_update_history("cloud")
    assert cloud_history == ["v2"]

def test_help_backend_contract():
    backend = HelpBackendContract()
    assert backend.update_state == UpdateState.INSTALLED
    
    backend.publish_update("2.0.0")
    assert backend.update_state == UpdateState.AVAILABLE
    assert backend.pending_update_version == "2.0.0"
    
    backend.acknowledge_update_ready()
    assert backend.update_state == UpdateState.READY_TO_INSTALL
    
    ticket = backend.create_support_ticket("t1", "crash")
    assert ticket.status == "OPEN"
    assert backend.tickets["t1"].issue_type == "crash"

import pytest
from courier_core.host_registry import (
    HostCapabilityRegistry, WorkkeyRequirements
)

def test_eligible_hosts_deterministic_selection():
    registry = HostCapabilityRegistry()
    registry.register_host("node-beta", "linux", {"network", "cloud"})
    registry.register_host("node-alpha", "linux", {"network", "cloud"})
    registry.register_host("node-gamma", "linux", {"network"}) # Missing cloud
    
    req = WorkkeyRequirements(required_os="linux", required_capabilities={"network", "cloud"})
    
    result = registry.find_eligible_hosts(req)
    
    # Must be a list and deterministically sorted regardless of insertion order
    assert isinstance(result, list)
    assert result == ["node-alpha", "node-beta"]

def test_blocked_right_host_when_no_match():
    registry = HostCapabilityRegistry()
    registry.register_host("win-1", "windows", {"GUI", "local_file_access"})
    registry.register_host("mac-1", "macos", {"GUI", "browser"})
    
    req = WorkkeyRequirements(required_capabilities={"long_running", "cloud"})
    
    assert registry.find_eligible_hosts(req) == "BLOCKED_RIGHT_HOST"

def test_os_mismatch_blocks_host():
    registry = HostCapabilityRegistry()
    registry.register_host("win-1", "windows", {"network"})
    registry.register_host("linux-1", "linux", {"network"})
    
    req = WorkkeyRequirements(required_os="linux", required_capabilities={"network"})
    
    assert registry.find_eligible_hosts(req) == ["linux-1"]

def test_no_os_requirement_accepts_any_os():
    registry = HostCapabilityRegistry()
    registry.register_host("win-1", "windows", {"browser"})
    registry.register_host("mac-1", "macos", {"browser"})
    
    req = WorkkeyRequirements(required_capabilities={"browser"})
    
    assert registry.find_eligible_hosts(req) == ["mac-1", "win-1"]

def test_empty_registry_blocks():
    registry = HostCapabilityRegistry()
    req = WorkkeyRequirements(required_capabilities={"network"})
    
    assert registry.find_eligible_hosts(req) == "BLOCKED_RIGHT_HOST"

def test_deregister_removes_eligibility():
    registry = HostCapabilityRegistry()
    registry.register_host("mac-1", "macos", {"network"})
    
    req = WorkkeyRequirements(required_capabilities={"network"})
    assert registry.find_eligible_hosts(req) == ["mac-1"]
    
    registry.deregister_host("mac-1")
    assert registry.find_eligible_hosts(req) == "BLOCKED_RIGHT_HOST"

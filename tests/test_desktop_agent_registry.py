"""Agent Registry directory tests (no execution, no control)."""
import pytest

from courier_desktop.agent_registry import AgentRegistry, PROVIDERS


def test_register_and_get_roundtrip():
    registry = AgentRegistry()
    record = registry.register("muse-1", "muse", persistent=True, capabilities=["audit"])
    assert record["status"] == "IDLE"
    assert record["persistent"] is True
    assert registry.get("muse-1")["provider"] == "muse"


def test_register_rejects_duplicate_and_unknown_provider():
    registry = AgentRegistry()
    registry.register("muse-1", "muse")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("muse-1", "muse")
    with pytest.raises(ValueError, match="unknown provider"):
        registry.register("x-1", "nope")


def test_register_rejects_bad_capabilities():
    registry = AgentRegistry()
    with pytest.raises(ValueError, match="capabilities"):
        registry.register("muse-1", "muse", capabilities=["ok", ""])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_all_vision_providers_accepted(provider):
    registry = AgentRegistry()
    assert registry.register(f"agent-{provider}", provider)["provider"] == provider


def test_heartbeat_updates_status_and_time():
    registry = AgentRegistry()
    registry.register("muse-1", "muse")
    record = registry.heartbeat("muse-1", "RUNNING", now=1234.0)
    assert record["status"] == "RUNNING"
    assert record["last_heartbeat"] == 1234.0
    with pytest.raises(ValueError, match="unknown agent status"):
        registry.heartbeat("muse-1", "FLYING")
    with pytest.raises(ValueError, match="unknown agent"):
        registry.heartbeat("ghost", "RUNNING")


def test_deregister_removes_and_rejects_unknown():
    registry = AgentRegistry()
    registry.register("muse-1", "muse")
    registry.deregister("muse-1")
    with pytest.raises(ValueError, match="unknown agent"):
        registry.get("muse-1")
    with pytest.raises(ValueError, match="unknown agent"):
        registry.deregister("muse-1")


def test_list_filters_provider_and_persistent():
    registry = AgentRegistry()
    registry.register("muse-1", "muse", persistent=True)
    registry.register("muse-2", "muse")
    registry.register("claude-1", "claude", persistent=True)
    assert len(registry.list()) == 3
    assert len(registry.list(provider="muse")) == 2
    assert {r["agent_id"] for r in registry.list(persistent_only=True)} == {"muse-1", "claude-1"}
    with pytest.raises(ValueError, match="unknown provider"):
        registry.list(provider="nope")


def test_records_are_copies():
    registry = AgentRegistry()
    registry.register("muse-1", "muse")
    registry.get("muse-1")["status"] = "RUNNING"
    assert registry.get("muse-1")["status"] == "IDLE"

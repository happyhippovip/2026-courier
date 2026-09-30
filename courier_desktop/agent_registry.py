"""Desktop overlay: Agent Registry (directory only).

The registry records which agents exist, which provider they belong to, and
whether they run persistently (infinity-hat: autonomous workers). It never
steers, starts, stops, or otherwise controls any agent; it is a read/write
directory with validation.
"""

from __future__ import annotations

import time
from typing import Any

PROVIDERS = ("muse", "claude", "gemini", "antigravity", "windows", "github", "simulated")
AGENT_STATUSES = ("IDLE", "CLAIMED", "RUNNING", "BLOCKED", "OFFLINE")


def _require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{field} must be a non-empty string (<=128)")
    return value


class AgentRegistry:
    """In-memory agent directory. No execution, no control."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}

    def register(self, agent_id: str, provider: str, persistent: bool = False,
                 capabilities: list[str] | None = None) -> dict[str, Any]:
        """Add an agent. Raises when the id is taken or the provider unknown."""
        _require_id(agent_id, "agent_id")
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        if agent_id in self._agents:
            raise ValueError(f"agent {agent_id!r} already registered")
        caps = list(capabilities) if capabilities else []
        if any(not isinstance(c, str) or not c for c in caps):
            raise ValueError("capabilities must be non-empty strings")
        record = {
            "agent_id": agent_id,
            "provider": provider,
            "persistent": bool(persistent),
            "capabilities": caps,
            "status": "IDLE",
            "last_heartbeat": None,
        }
        self._agents[agent_id] = record
        return dict(record)

    def heartbeat(self, agent_id: str, status: str = "RUNNING", now: float | None = None) -> dict[str, Any]:
        """Record liveness. Unknown ids raise; unknown statuses raise."""
        _require_id(agent_id, "agent_id")
        if status not in AGENT_STATUSES:
            raise ValueError(f"unknown agent status {status!r}")
        try:
            record = self._agents[agent_id]
        except KeyError:
            raise ValueError(f"unknown agent {agent_id!r}") from None
        record["status"] = status
        record["last_heartbeat"] = time.time() if now is None else now
        return dict(record)

    def get(self, agent_id: str) -> dict[str, Any]:
        _require_id(agent_id, "agent_id")
        try:
            return dict(self._agents[agent_id])
        except KeyError:
            raise ValueError(f"unknown agent {agent_id!r}") from None

    def deregister(self, agent_id: str) -> None:
        _require_id(agent_id, "agent_id")
        try:
            del self._agents[agent_id]
        except KeyError:
            raise ValueError(f"unknown agent {agent_id!r}") from None

    def list(self, provider: str | None = None, persistent_only: bool = False) -> list[dict[str, Any]]:
        """List agents, optionally filtered. Returns copies."""
        if provider is not None and provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        return [
            dict(record)
            for record in self._agents.values()
            if (provider is None or record["provider"] == provider)
            and (not persistent_only or record["persistent"])
        ]

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class AgentCatalogEntry:
    id: str
    display_name: str
    agent_class: str
    status: str
    owner_files: List[str]
    capabilities: List[str]
    write_authority: bool
    read_only_default: bool
    supported_hosts: List[str]
    provider_binding: Optional[str]
    cost_class: str
    heavy_job_class: Optional[str]
    evidence_sources: List[str] = field(default_factory=list)

@dataclass
class AgentCatalog:
    schema_version: str
    authority: str
    related_issues: List[int]
    agents: List[AgentCatalogEntry]

    @classmethod
    def load(cls, path: Path) -> 'AgentCatalog':
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        agents = []
        for a_data in data.get("agents", []):
            agents.append(AgentCatalogEntry(
                id=a_data["id"],
                display_name=a_data["display_name"],
                agent_class=a_data["class"],
                status=a_data["status"],
                owner_files=a_data.get("owner_files", []),
                capabilities=a_data.get("capabilities", []),
                write_authority=a_data.get("write_authority", False),
                read_only_default=a_data.get("read_only_default", True),
                supported_hosts=a_data.get("supported_hosts", []),
                provider_binding=a_data.get("provider_binding"),
                cost_class=a_data.get("cost_class", "unknown"),
                heavy_job_class=a_data.get("heavy_job_class"),
                evidence_sources=a_data.get("evidence_sources", [])
            ))
            
        return cls(
            schema_version=data.get("schema_version", ""),
            authority=data.get("authority", ""),
            related_issues=data.get("related_issues", []),
            agents=agents
        )

@dataclass
class RoutingExplanation:
    selected_agent_id: str
    capable_reason: str
    non_duplicate_reason: str
    cost_reason: str
    fallback_agent_id: Optional[str]

class CapabilitySelector:
    def __init__(self, catalog: AgentCatalog):
        self.catalog = catalog
        
    def select_agent_for_task(self, required_capability: str, required_host: Optional[str] = None, current_owners: List[str] = None, require_implemented: bool = True) -> RoutingExplanation:
        if current_owners is None:
            current_owners = []
            
        candidates = []
        for agent in self.catalog.agents:
            if require_implemented and agent.status != "implemented":
                continue
            if required_capability in agent.capabilities:
                if required_host is None or not agent.supported_hosts or required_host in agent.supported_hosts:
                    # Exclude active owners to prevent duplicate writers
                    if agent.id in current_owners:
                        continue
                    
                    # Also exclude if any of its owner_files are claimed by current_owners
                    active_owner_files = set()
                    for owner_id in current_owners:
                        for a in self.catalog.agents:
                            if a.id == owner_id:
                                active_owner_files.update(a.owner_files)
                    
                    if set(agent.owner_files).intersection(active_owner_files):
                        continue
                        
                    candidates.append(agent)
                    
        if not candidates:
            raise ValueError(f"No agent found for capability {required_capability} (or all capable agents are blocked by duplicate writer constraints)")
            
        # Sort by cost (local > free > low > medium > high > routed)
        # Sort by class (core > specialist > provider > reserve)
        cost_ranks = {"local_first": 0, "free": 1, "low": 2, "medium": 3, "high": 4, "local_or_routed": 5}
        class_ranks = {"core": 0, "specialist": 1, "provider": 2, "reserve": 3}
        
        candidates.sort(key=lambda a: (
            class_ranks.get(a.agent_class, 99),
            cost_ranks.get(a.cost_class, 99)
        ))
        
        selected = candidates[0]
        fallback = candidates[1].id if len(candidates) > 1 else None
        
        return RoutingExplanation(
            selected_agent_id=selected.id,
            capable_reason=f"Agent declares capability '{required_capability}' in catalog",
            non_duplicate_reason=f"Respects one-writer constraint; active owners: {current_owners}",
            cost_reason=f"Selected cheapest available option (cost class: {selected.cost_class})",
            fallback_agent_id=fallback
        )

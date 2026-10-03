from typing import Dict, Set, List
from dataclasses import dataclass

@dataclass
class UpdateDelta:
    update_id: str
    capabilities_added: Set[str]
    capabilities_removed: Set[str]

class SemanticDeltaRegistry:
    """MAC-23: Track capabilities affected by updates."""
    def __init__(self):
        self._deltas: List[UpdateDelta] = []
        self._current_capabilities: Set[str] = set()

    def register_update(self, delta: UpdateDelta) -> None:
        self._deltas.append(delta)
        self._current_capabilities.update(delta.capabilities_added)
        self._current_capabilities.difference_update(delta.capabilities_removed)

    def get_current_capabilities(self) -> Set[str]:
        return set(self._current_capabilities)

    def query_update_history(self, capability: str) -> List[str]:
        """Returns list of update_ids that modified this capability."""
        history = []
        for d in self._deltas:
            if capability in d.capabilities_added or capability in d.capabilities_removed:
                history.append(d.update_id)
        return history

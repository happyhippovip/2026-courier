from typing import List, Optional
from courier_core.readiness import ReadinessState

class ReadinessNode:
    """MAC-11: Readiness Tree Core - Evidence-derived readiness only."""
    def __init__(self, name: str, state: ReadinessState = ReadinessState.SPECIFIED):
        self.name = name
        self._state = state
        self.children: List['ReadinessNode'] = []

    def add_child(self, node: 'ReadinessNode') -> None:
        self.children.append(node)

    def set_local_state(self, state: ReadinessState) -> None:
        self._state = state

    def compute_state(self) -> ReadinessState:
        """Parent readiness is constrained by the lowest readiness of its dependencies."""
        if not self.children:
            return self._state
        
        lowest_child_state = min(child.compute_state() for child in self.children)
        return min(self._state, lowest_child_state)

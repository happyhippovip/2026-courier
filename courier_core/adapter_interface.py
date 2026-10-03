from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProviderAdapter(ABC):
    """MAC-19: Generic Adapter Interface for Contract Tests."""
    @abstractmethod
    def connect(self) -> bool:
        pass
        
    @abstractmethod
    def execute_action(self, action_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def verify_side_effect(self, action_name: str, payload: Dict[str, Any]) -> bool:
        pass

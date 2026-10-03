from enum import Enum, auto

class MarketingAction(Enum):
    PREPARE = auto()
    PREVIEW = auto()
    PUBLISH = auto()
    SPEND = auto()

class MarketingAuthorityBoundary:
    """WK-20: Implement only safe prepare/preview contracts. No publication and no spend."""
    @staticmethod
    def execute(action: MarketingAction, payload: dict) -> dict:
        if action in (MarketingAction.PUBLISH, MarketingAction.SPEND):
            raise PermissionError(f"Action {action.name} strictly forbidden by Marketing Authority Boundary.")
        
        return {
            "status": "SUCCESS",
            "action": action.name,
            "preview_data": payload
        }

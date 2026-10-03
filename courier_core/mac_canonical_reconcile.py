from typing import List, Dict
from datetime import datetime

class CanonicalReconciler:
    """MAC-30: Reconcile all completed work against current canonical memory."""
    def __init__(self, completed_workkeys: List[str]):
        self.completed = set(completed_workkeys)
        self.missing: List[str] = []

    def reconcile_against_target(self, target_keys: List[str]) -> Dict[str, any]:
        for key in target_keys:
            if key not in self.completed:
                self.missing.append(key)
        
        is_ready = len(self.missing) == 0
        return {
            "reconciliation_time": datetime.utcnow().isoformat(),
            "target_count": len(target_keys),
            "completed_count": len(self.completed),
            "missing": self.missing,
            "status": "CONTINUATION_MODE" if is_ready else "PENDING_RECONCILIATION"
        }

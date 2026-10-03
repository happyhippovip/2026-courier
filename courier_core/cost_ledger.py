from dataclasses import dataclass, field
from typing import Dict, List
from collections import defaultdict

@dataclass
class CostEntry:
    workkey: str
    resource_type: str # 'tokens', 'compute', 'tool'
    amount: float
    cost_usd: float

class CostLedger:
    """MAC-14: Track model/tool/runtime cost at workkey level."""
    def __init__(self):
        self.entries: List[CostEntry] = []

    def record_cost(self, workkey: str, resource_type: str, amount: float, cost_usd: float) -> None:
        self.entries.append(CostEntry(workkey, resource_type, amount, cost_usd))

    def get_total_for_workkey(self, workkey: str) -> float:
        return sum(e.cost_usd for e in self.entries if e.workkey == workkey)

    def get_total_project_cost(self) -> float:
        return sum(e.cost_usd for e in self.entries)

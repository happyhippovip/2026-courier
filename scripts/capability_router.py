import dataclasses
from typing import List, Optional, Dict, Any

class Capability:
    DETERMINISTIC_CI = "deterministic_ci"
    GITHUB_REPO_WORKER = "github_repo_worker"
    CHEAP_REASONING_WORKER = "cheap_reasoning_worker"
    STRONG_CODE_WORKER = "strong_code_worker"
    VERIFIER = "verifier"
    WINDOWS_DESKTOP_WORKER = "windows_desktop_worker"
    MAC_DESKTOP_WORKER = "mac_desktop_worker"
    SSH_REMOTE_WORKER = "ssh_remote_worker"
    BROWSER_WORKER = "browser_worker"
    HUMAN = "human"

@dataclasses.dataclass
class WorkerProfile:
    worker_id: str
    capabilities: List[str]
    cost_per_unit: float
    is_available: bool = True

def select_best_worker(required_capabilities: List[str], available_workers: List[WorkerProfile]) -> Optional[WorkerProfile]:
    """
    Selects the cheapest available worker that satisfies ALL required capabilities.
    Preference order based on capabilities:
    1. Deterministic / CI
    2. GitHub-native
    3. Cheapest qualified
    4. Stronger model (if needed)
    """
    if not required_capabilities or not available_workers:
        return None
        
    qualified_workers = []
    for worker in available_workers:
        if not worker.is_available:
            continue
        # Check if worker has all required capabilities
        if all(cap in worker.capabilities for cap in required_capabilities):
            qualified_workers.append(worker)
            
    if not qualified_workers:
        return None
        
    # Sort by cost ascending
    qualified_workers.sort(key=lambda w: w.cost_per_unit)
    
    # We can refine this logic if we want to explicitly prefer deterministic CI even if it costs slightly more,
    # but normally deterministic CI has the lowest cost (e.g. 0.0 or compute cost vs API token cost).
    # Assuming cost_per_unit reflects the preference order appropriately.
    
    return qualified_workers[0]

import dataclasses
from enum import Enum
from typing import List, Optional

class RecommendationType(str, Enum):
    NONE = "NONE"
    USE_EXISTING_AGENT = "USE_EXISTING_AGENT"
    SWITCH_AVAILABLE_PROVIDER = "SWITCH_AVAILABLE_PROVIDER"
    ADD_MODEL_CAPACITY = "ADD_MODEL_CAPACITY"
    ADD_COMPUTE = "ADD_COMPUTE"
    HUMAN_ACTION = "HUMAN_ACTION"
    DO_NOT_BUY = "DO_NOT_BUY"

class Severity(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED_ACCELERATION_OPPORTUNITY = "RED / ACCELERATION_OPPORTUNITY"

@dataclasses.dataclass
class Recommendation:
    severity: Severity
    type: RecommendationType
    blocked_task: Optional[str] = None
    reason_existing_cannot_execute: Optional[str] = None
    proposed_capability: Optional[str] = None
    known_cost: str = "UNKNOWN"
    acceleration_evidence: Optional[str] = None
    duplication_risk: Optional[str] = None
    human_approval_required: bool = False

def analyze_capacity_and_recommend(
    active_tasks: List[str],
    blocked_tasks: List[dict],
    available_workers: List[dict]
) -> Recommendation:
    """
    Analyzes the current ledger state to recommend if extra capacity is needed.
    
    If no blocked tasks, return GREEN/NONE.
    If adding capacity would only duplicate work, return YELLOW/DO_NOT_BUY.
    """
    if not blocked_tasks:
        return Recommendation(
            severity=Severity.GREEN,
            type=RecommendationType.NONE
        )
        
    # Evaluate blocked tasks
    for task in blocked_tasks:
        task_id = task.get("mission_id", "UNKNOWN_TASK")
        capability_needed = task.get("capability_required", "UNKNOWN_CAPABILITY")
        
        # Check if we have an available worker that matches
        matching_workers = [
            w for w in available_workers 
            if capability_needed in w.get("capabilities", [])
        ]
        
        if matching_workers:
            # We have workers, maybe they are busy
            busy_workers = [w for w in matching_workers if w.get("busy", False)]
            if len(busy_workers) == len(matching_workers):
                # All qualified workers are busy
                return Recommendation(
                    severity=Severity.RED_ACCELERATION_OPPORTUNITY,
                    type=RecommendationType.ADD_COMPUTE,
                    blocked_task=task_id,
                    reason_existing_cannot_execute="All qualified workers for capability are currently busy.",
                    proposed_capability=capability_needed,
                    known_cost="UNKNOWN",
                    acceleration_evidence=f"Task {task_id} is blocked waiting for {capability_needed}.",
                    duplication_risk="LOW",
                    human_approval_required=True
                )
            else:
                return Recommendation(
                    severity=Severity.YELLOW,
                    type=RecommendationType.USE_EXISTING_AGENT,
                    blocked_task=task_id,
                    reason_existing_cannot_execute="Qualified workers exist but task is not assigned.",
                    proposed_capability=capability_needed,
                    human_approval_required=False
                )
                
        else:
            # No worker has this capability
            return Recommendation(
                severity=Severity.RED_ACCELERATION_OPPORTUNITY,
                type=RecommendationType.ADD_MODEL_CAPACITY,
                blocked_task=task_id,
                reason_existing_cannot_execute=f"No existing worker provides capability {capability_needed}.",
                proposed_capability=capability_needed,
                known_cost="UNKNOWN",
                acceleration_evidence=f"Task {task_id} requires {capability_needed} which is missing.",
                duplication_risk="LOW",
                human_approval_required=True
            )

    return Recommendation(
        severity=Severity.YELLOW,
        type=RecommendationType.DO_NOT_BUY,
        blocked_task="MULTIPLE",
        reason_existing_cannot_execute="Adding capacity would only duplicate active work.",
        human_approval_required=False
    )

def save_advisor_state(recommendation: Recommendation, events_dir: str):
    import json
    import os
    target_dir = os.path.join(events_dir, "acceleration_advisor")
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, "advisor_state.json")
    
    state = dataclasses.asdict(recommendation)
    with open(target_file, "w") as f:
        json.dump(state, f, indent=2)

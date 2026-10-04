from dataclasses import dataclass
from typing import Dict, Any, Callable
import datetime

@dataclass
class StaleDetectionResult:
    is_stale: bool
    reason: str = ""

def detect_stale_pr_head(stored_pr_head: str, current_pr_head: str) -> StaleDetectionResult:
    if stored_pr_head and current_pr_head and stored_pr_head != current_pr_head:
        return StaleDetectionResult(True, f"Stored PR head ({stored_pr_head}) does not match current PR head ({current_pr_head})")
    return StaleDetectionResult(False)

def detect_stale_sha(stored_sha: str, branch_head_sha: str) -> StaleDetectionResult:
    if stored_sha and branch_head_sha and stored_sha != branch_head_sha:
        return StaleDetectionResult(True, f"Stored SHA ({stored_sha}) does not match branch head ({branch_head_sha})")
    return StaleDetectionResult(False)

def detect_stale_test_result(stored_binary_hash: str, current_binary_hash: str) -> StaleDetectionResult:
    if stored_binary_hash and current_binary_hash and stored_binary_hash != current_binary_hash:
        return StaleDetectionResult(True, f"Test result applies to older binary ({stored_binary_hash} != {current_binary_hash})")
    return StaleDetectionResult(False)

def detect_expired_writer_ownership(stored_timestamp: str, max_age_hours: int, current_timestamp: str = None) -> StaleDetectionResult:
    if not stored_timestamp:
        return StaleDetectionResult(False)
    
    try:
        stored_dt = datetime.datetime.fromisoformat(stored_timestamp.replace('Z', '+00:00'))
        if current_timestamp:
            current_dt = datetime.datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
        else:
            current_dt = datetime.datetime.now(datetime.timezone.utc)
            
        age = (current_dt - stored_dt).total_seconds() / 3600.0
        
        if age > max_age_hours:
            return StaleDetectionResult(True, f"Writer ownership expired (age {age:.1f}h > max {max_age_hours}h)")
    except ValueError:
        return StaleDetectionResult(False, "Invalid timestamp format")
        
    return StaleDetectionResult(False)

def detect_disappeared_blocker(stored_blocker_id: str, current_active_blockers: list) -> StaleDetectionResult:
    if stored_blocker_id and stored_blocker_id not in current_active_blockers:
        return StaleDetectionResult(True, f"Stored blocker '{stored_blocker_id}' is no longer in active blockers list")
    return StaleDetectionResult(False)

class StaleMemoryDetector:
    def __init__(self, fetchers: Dict[str, Callable[[], Any]]):
        """
        fetchers is a dictionary mapping a context key to a function that retrieves current state.
        Keys expected: 'current_pr_head', 'branch_head_sha', 'current_binary_hash', 'current_active_blockers', 'current_timestamp'
        """
        self.fetchers = fetchers

    def evaluate_claim(self, claim_data: Dict[str, Any]) -> StaleDetectionResult:
        """
        Evaluates a structured memory claim for staleness across multiple rules.
        """
        # Rule 1: PR Head
        if "pr_head" in claim_data and "current_pr_head" in self.fetchers:
            res = detect_stale_pr_head(claim_data["pr_head"], self.fetchers["current_pr_head"]())
            if res.is_stale: return res
            
        # Rule 2: SHA
        if "sha" in claim_data and "branch_head_sha" in self.fetchers:
            res = detect_stale_sha(claim_data["sha"], self.fetchers["branch_head_sha"]())
            if res.is_stale: return res
            
        # Rule 3: Binary Test Result
        if "binary_hash" in claim_data and "current_binary_hash" in self.fetchers:
            res = detect_stale_test_result(claim_data["binary_hash"], self.fetchers["current_binary_hash"]())
            if res.is_stale: return res
            
        # Rule 4: Writer Ownership
        if "writer_timestamp" in claim_data:
            current_ts = self.fetchers.get("current_timestamp", lambda: None)()
            res = detect_expired_writer_ownership(claim_data["writer_timestamp"], 4.0, current_ts) # 4 hours max
            if res.is_stale: return res
            
        # Rule 5: Blocker
        if "blocker_id" in claim_data and "current_active_blockers" in self.fetchers:
            res = detect_disappeared_blocker(claim_data["blocker_id"], self.fetchers["current_active_blockers"]())
            if res.is_stale: return res
            
        return StaleDetectionResult(False)

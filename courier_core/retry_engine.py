from dataclasses import dataclass
from courier_core.adapter_errors import AdapterError, ErrorSeverity

@dataclass
class RetryPolicy:
    max_retries: int
    base_backoff_sec: float

class RetryEngine:
    """MAC-07: Typed retry/backoff/failure classification."""
    def __init__(self, default_policy: RetryPolicy):
        self.default_policy = default_policy

    def calculate_action(self, error: Exception, attempt: int) -> dict:
        if not isinstance(error, AdapterError):
            return {"action": "FAIL", "reason": "UNCLASSIFIED_ERROR"}
            
        if error.severity == ErrorSeverity.FATAL:
            return {"action": "FAIL", "reason": "FATAL_SEVERITY"}
            
        if error.severity == ErrorSeverity.REQUIRES_USER:
            return {"action": "ESCALATE", "reason": "NEEDS_HUMAN"}
            
        # Transient errors
        if attempt >= self.default_policy.max_retries:
            return {"action": "FAIL", "reason": "MAX_RETRIES_EXCEEDED"}
            
        backoff = self.default_policy.base_backoff_sec * (2 ** attempt)
        return {"action": "RETRY", "delay_sec": backoff}

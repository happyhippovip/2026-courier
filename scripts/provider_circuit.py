import enum
from dataclasses import dataclass
import datetime

class ProviderState(enum.Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RECOVERY_PROBE_DUE = "RECOVERY_PROBE_DUE"

class ErrorCategory(enum.Enum):
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_ERROR = "AUTH_ERROR"
    UNKNOWN = "UNKNOWN"

@dataclass
class CircuitState:
    state: ProviderState = ProviderState.AVAILABLE
    reset_time: datetime.datetime = None
    probe_in_flight: bool = False

    @staticmethod
    def _as_aware(value: datetime.datetime):
        """Normalize reset timestamps to aware UTC.

        Provider reset headers and ledger-restored timestamps are often
        naive; comparing them against aware ``now`` raises TypeError and
        would crash the scheduler path. Assume UTC for naive values.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value

    def classify_error(self, error_code: int, error_message: str):
        msg = error_message.lower()
        if error_code == 429:
            if "quota" in msg or "exhausted" in msg:
                return ErrorCategory.QUOTA_EXHAUSTED
            return ErrorCategory.RATE_LIMITED
        if error_code in (401, 403):
            return ErrorCategory.AUTH_ERROR
        if error_code >= 500:
            return ErrorCategory.UNAVAILABLE
        if "quota" in msg or "exhausted" in msg:
            return ErrorCategory.QUOTA_EXHAUSTED
        return ErrorCategory.UNKNOWN

    def record_failure(self, error_code: int, error_message: str, reset_time: datetime.datetime = None):
        category = self.classify_error(error_code, error_message)
        
        if category == ErrorCategory.QUOTA_EXHAUSTED:
            self.state = ProviderState.QUOTA_EXHAUSTED
        elif category == ErrorCategory.RATE_LIMITED:
            self.state = ProviderState.RATE_LIMITED
        elif category == ErrorCategory.UNAVAILABLE:
            self.state = ProviderState.PROVIDER_UNAVAILABLE
        elif category == ErrorCategory.AUTH_ERROR:
            self.state = ProviderState.AUTH_REQUIRED
        else:
            self.state = ProviderState.DEGRADED
            
        if reset_time:
            self.reset_time = self._as_aware(reset_time)

        # A fresh failure supersedes any outstanding recovery probe.
        self.probe_in_flight = False

    def check_circuit(self) -> bool:
        """Returns True if open (prevent requests), False if closed (allow requests)"""
        if self.state in (ProviderState.AVAILABLE, ProviderState.DEGRADED):
            return False

        if self.state in (ProviderState.QUOTA_EXHAUSTED, ProviderState.RATE_LIMITED, ProviderState.PROVIDER_UNAVAILABLE):
            # Check if reset time has passed
            reset = self._as_aware(self.reset_time)
            if reset and datetime.datetime.now(datetime.timezone.utc) >= reset:
                self.state = ProviderState.RECOVERY_PROBE_DUE
                return False
            return True
            
        if self.state == ProviderState.RECOVERY_PROBE_DUE:
            return False
            
        if self.state == ProviderState.AUTH_REQUIRED:
            return True
            
        return False

    def claim_probe(self) -> bool:
        """Claim the single bounded recovery probe.

        Returns True exactly once per RECOVERY_PROBE_DUE episode; further
        claimants must wait instead of firing duplicate provider probes.
        The claim releases on the next recorded success or failure.
        """
        if self.state == ProviderState.RECOVERY_PROBE_DUE and not self.probe_in_flight:
            self.probe_in_flight = True
            return True
        return False

    def record_success(self):
        self.state = ProviderState.AVAILABLE
        self.reset_time = None
        self.probe_in_flight = False

class ProviderCircuitBreaker:
    def __init__(self):
        self.circuits: dict[str, CircuitState] = {}
        
    def get_circuit(self, provider_id: str, capability: str) -> CircuitState:
        key = f"{provider_id}|{capability}"
        if key not in self.circuits:
            self.circuits[key] = CircuitState()
        return self.circuits[key]
        
    def is_open(self, provider_id: str, capability: str) -> bool:
        return self.get_circuit(provider_id, capability).check_circuit()
        
    def record_failure(self, provider_id: str, capability: str, error_code: int, error_message: str, reset_time: datetime.datetime = None):
        self.get_circuit(provider_id, capability).record_failure(error_code, error_message, reset_time)
        
    def record_success(self, provider_id: str, capability: str):
        self.get_circuit(provider_id, capability).record_success()


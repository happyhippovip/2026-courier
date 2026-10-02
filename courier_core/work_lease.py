import time
from dataclasses import dataclass

class LeaseError(Exception):
    pass

class LeaseDeniedError(LeaseError):
    pass

class LeaseNotFoundError(LeaseError):
    pass

class UnauthorizedReleaseError(LeaseError):
    pass

@dataclass
class WorkLease:
    scope: str
    writer: str
    host: str
    workkey: str
    mode: str
    acquired_at: float
    expiry: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expiry

class WorkLeaseManager:
    def __init__(self):
        self._write_leases: dict[str, WorkLease] = {}

    def _now(self) -> float:
        return time.time()

    def acquire(self, scope: str, writer: str, host: str, workkey: str, mode: str = "WRITE", ttl: float = 60.0, now: float = None) -> WorkLease:
        t = now if now is not None else self._now()

        # Read-only work is unaffected by write locks, or simply tracked ephemerally
        if mode == "READ":
            return WorkLease(scope, writer, host, workkey, mode, t, t + ttl)

        current = self._write_leases.get(scope)
        
        # If there's an active write lease owned by someone else
        if current and not current.is_expired(t):
            if current.writer != writer:
                raise LeaseDeniedError(f"Scope '{scope}' is locked by writer '{current.writer}'")
            else:
                # Re-acquire / extend existing lock if same writer
                current.expiry = t + ttl
                current.host = host
                current.workkey = workkey
                return current

        # Expired or empty -> grant new lease
        lease = WorkLease(scope, writer, host, workkey, mode, t, t + ttl)
        self._write_leases[scope] = lease
        return lease

    def heartbeat(self, scope: str, writer: str, ttl: float = 60.0, now: float = None) -> None:
        t = now if now is not None else self._now()
        current = self._write_leases.get(scope)
        if not current:
            raise LeaseNotFoundError("No lease found for this scope")
        if current.writer != writer:
            raise LeaseDeniedError("Not the lease owner")
        
        current.expiry = t + ttl

    def release(self, scope: str, writer: str) -> None:
        current = self._write_leases.get(scope)
        if not current:
            return  # Idempotent release
        if current.writer != writer:
            raise UnauthorizedReleaseError("Wrong owner cannot release lease")
        
        del self._write_leases[scope]

    def steal(self, scope: str, new_writer: str, host: str, workkey: str, ttl: float = 60.0, now: float = None) -> WorkLease:
        """Forcefully takes over a lease regardless of expiry (recovery rule)."""
        t = now if now is not None else self._now()
        lease = WorkLease(scope, new_writer, host, workkey, "WRITE", t, t + ttl)
        self._write_leases[scope] = lease
        return lease

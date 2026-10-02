# L12: UNKNOWN_2XX_HARDENING

## Objective
Design and enforce strict unknown/empty 2xx behavior in the worker's HTTP client. Prevent intermediaries (proxies, load balancers, captive portals) from forging application truth via arbitrary 2xx responses.

## Analysis
The `ControllerClient` in `courier_worker/service.py` is vulnerable to infrastructure returning arbitrary 200 OK responses. For example, in `claim()`:
```python
        if status == 204:
            return None
        if status == 200 and isinstance(payload, dict):
            return payload
        return None
```
If a proxy intercepts the request and returns an empty 200 OK, the payload is not a dictionary. The method falls through and returns `None`.

**The Danger**: Returning `None` is the semantically valid signal for "the queue is empty". The worker will silently loop and sleep, hiding the fact that it is completely disconnected from the actual L2 Controller. The correct behavior for *any* unexpected HTTP response is to raise a `ControllerError`, which engages the worker's exponential backoff and observability paths for infrastructure faults.

## Implementation Handoff (Fix Packet)

### Hardening `claim`
Only exactly `204` or exactly `200` with a valid dictionary are allowed. All other responses must raise.

**File: `courier_worker/service.py`**
```python
<<<<
    def claim(self, worker_id: str) -> Optional[dict]:
        try:
            status, payload = self._call("POST", "/claim", {"worker_id": worker_id})
        except ControllerError:
            return None
        if status == 204:
            return None
        if status == 200 and isinstance(payload, dict):
            return payload
        return None
====
    def claim(self, worker_id: str) -> Optional[dict]:
        try:
            status, payload = self._call("POST", "/claim", {"worker_id": worker_id})
        except ControllerError:
            return None
        if status == 204:
            return None
        if status == 200 and isinstance(payload, dict):
            return payload
        # UNKNOWN 2XX HARDENING: Do not mask proxy/infrastructure errors as "no work".
        raise ControllerError(f"claim: unexpected response status {status} or payload shape")
>>>>
```

*(Note: The L11 packet already hardened `deliver()`. Similar strict assertions should be added to `health()` and `heartbeat()` as part of this complete L12 push.)*

## Evidence & Verification
A red test `tests/test_l12_unknown_2xx_hardening.py` has been committed to branch `ledger/L12-unknown-2xx-hardening`. It mocks the HTTP call to return an empty 200 and proves that `claim()` incorrectly returns `None` (no work). Applying this fix packet causes the test to fail by raising a `ControllerError` as mathematically required.

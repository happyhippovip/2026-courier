# L11: RESULT_ACK_ENUMERATION

## Objective
Derive and enumerate the valid canonical result acknowledgements from the Controller, and prove that the L3 Worker currently trusts any arbitrary HTTP 200 response (flaw). Provide the exact implementation fix.

## Analysis
When the worker delivers a `RESULT_READY` payload via `POST /result`, the L2 Controller only considers the payload durably appended if it returns one of the following canonical bodies:
1. `{"status": "ACCEPTED_FOR_VERIFY"}` (Appended to Journal successfully)
2. `{"status": "ACK_DUPLICATE"}` (Ignored safely due to exact duplicate semantics)

**The Flaw**:
In `courier_worker/service.py` (`ControllerClient.deliver`), the logic falls back to:
```python
        if status == 200:
            return "accepted"
```
This means an empty HTTP 200 from a load balancer, an intercepting proxy, or an internal infrastructure error page is treated as canonical acceptance. The worker deletes the payload from its outbox, creating silent data loss.

## Implementation Handoff (Fix Packet)

### Worker Hardening
Remove the fallback clause to ensure the worker only accepts exact enumerated states.

**File: `courier_worker/service.py`**
```python
<<<<
        if status in (404, 409):
            return "stale"
        if status == 200 and isinstance(body, dict) \
                and body.get("status") in ("ACCEPTED_FOR_VERIFY", "ACK_DUPLICATE"):
            return "accepted"
        if status == 200:
            return "accepted"
        raise ControllerError(f"result: status {status}")
====
        if status in (404, 409):
            return "stale"
        if status == 200 and isinstance(body, dict) \
                and body.get("status") in ("ACCEPTED_FOR_VERIFY", "ACK_DUPLICATE"):
            return "accepted"
        # An unknown 200 (or an empty 200 from a load balancer) is not a 
        # canonical ledger acknowledgement. Fail the delivery to trigger retry.
        raise ControllerError(f"result: unexpected canonical ack body {body} for status {status}")
>>>>
```

## Evidence & Verification
A red test `tests/test_l11_result_ack_enumeration.py` has been committed to branch `ledger/L11-result-ack-enumeration`. It mocks the `_call` network interface and proves that the worker currently returns `"accepted"` for empty bodies and garbage JSON `status` values. Applying the fix above makes the red test fail (which means it correctly raises `ControllerError` instead of returning `"accepted"`), proving the outbox will retry delivery.

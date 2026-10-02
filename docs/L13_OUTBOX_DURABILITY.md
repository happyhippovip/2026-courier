# L13: OUTBOX_DURABILITY

## Objective
Attack payload retention across transport ambiguity. Prove that the worker mistakenly destroys durable outbox payloads when encountering recoverable or ambiguous 409 HTTP conflicts, instead of retaining them. Provide the exact implementation fix.

## Analysis
The L3 Worker guarantees payload durability by writing results to a local `outbox` before attempting delivery. It correctly drops the payload from the outbox when the controller definitively acknowledges it (`ACCEPTED_FOR_VERIFY` or `ACK_DUPLICATE`) or when the controller definitively rejects the attempt as stale (`404` or `409 stale_dispatch`).

**The Flaw**:
In `courier_worker/service.py` (`ControllerClient.deliver`), the worker inspects the status code and blindly discards the payload on *any* 409:
```python
        if status in (404, 409):
            return "stale"
```
However, the L2 Controller emits several `409 Conflict` errors that do *not* mean the dispatch is stale. Most critically, if the worker's `POST /start` was lost to a network partition but the worker proceeded locally, the controller will reject the eventual `POST /result` with `409 not_started`. 

Because the worker blindly treats all 409s as `"stale"`, it permanently deletes the completed work from the outbox. This creates fatal data loss, destroying the only evidence of a completed execution.

## Implementation Handoff (Fix Packet)

### Worker Delivery Hardening
The worker must only return `"stale"` (which triggers outbox deletion) for the exact error codes that dictate the lease is gone. All other 409s are transport ambiguities or infrastructure faults and must raise `ControllerError` to retain the payload.

**File: `courier_worker/service.py`**
```python
<<<<
        if status in (404, 409):
            return "stale"
====
        if status == 404:
            return "stale"
        if status == 409 and isinstance(body, dict):
            code = body.get("code")
            if code in ("stale_dispatch", "cancel_requested"):
                return "stale"
            # 409 not_started or 409 result_conflict are transport ambiguities.
            # Retain the payload in the outbox by raising.
            raise ControllerError(f"result: transport ambiguity (409 {code}); retaining payload")
        if status == 409:
            raise ControllerError("result: unknown 409 conflict; retaining payload")
>>>>
```

*(Note: The controller could also be enhanced to automatically synthesize a `/start` event if a result arrives while `CLAIMED`, but the worker must never throw away evidence regardless).*

## Evidence & Verification
A red test `tests/test_l13_outbox_durability.py` has been committed to branch `ledger/L13-outbox-durability`. It simulates a `409 not_started` error from the controller and proves that the worker returns `"stale"`, causing `flush_outbox` to immediately unlink the durable outbox payload. Applying the fix above makes the test fail (by correctly raising a `ControllerError`), proving the payload will survive the transport ambiguity.

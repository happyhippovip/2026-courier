# MMAC-217 — Lane 4 cancel-contract audit (read-only)

Q1 from MMAC-216 resolved by reading the controller (integration/v1):
cancel() requests cooperative stop for live dispatches (TASK_CANCEL_REQUESTED;
worker notified via heartbeat; TASK_CANCELLED only on worker confirmation),
immediate cancel for QUEUED/BLOCKED. Late results/starts/claims fenced with
409. The hub's "stops at the next safe point" toast is an accurate summary.

Lane 4 customer-journey coverage is now complete; remaining items are all
owner-side. Re-arm on: #226-owner fix, owner answers, base change, new free key.

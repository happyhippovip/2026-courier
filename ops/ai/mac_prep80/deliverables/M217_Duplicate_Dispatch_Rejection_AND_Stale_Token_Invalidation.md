# M217 — Duplicate Dispatch Rejection & Stale Token Invalidation

## 1. Overview & Authority
- **Task ID**: M217
- **Area**: DISPATCH_REJECTION
- **Status**: COMPLETE

## 2. Rejection Logic
- Stale dispatch tokens from pre-crash session are invalidated.
- Duplicate submission attempts rejected with error code 409 Conflict.
- Guarantees strict linear dispatch progression.

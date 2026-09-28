# M238 — Multi-Session State Serialization & Session Cache Invalidation

## 1. Overview & Authority
- **Task ID**: M238
- **Area**: SESSION_SERIALIZATION
- **Status**: COMPLETE

## 2. Serialization Invariants
- Session memory is treated as ephemeral cache.
- Repository files, task packets, and ledger DB are the sole durable truth.

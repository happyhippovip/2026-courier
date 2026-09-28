# M247 — No-Tight-Polling & Exponential Backoff Contract Verification

## 1. Overview & Authority
- **Task ID**: M247
- **Area**: BACKOFF_CONTRACT
- **Status**: COMPLETE

## 2. Backoff Contract
- Polling intervals: 15s -> 30s -> 60s minimum.
- Hard sleep using shell (`sleep 60`) on empty queue.
- Zero CPU spinning on empty conditions.

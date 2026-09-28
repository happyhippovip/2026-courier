# M245 — Harvest Engine Conflict Resolution & Double-Claim Prevention

## 1. Overview & Authority
- **Task ID**: M245
- **Area**: HARVEST_ENGINE
- **Status**: COMPLETE

## 2. Prevention Protocol
- File-based atomic lock (`.claim.json` created with `O_EXCL`).
- Database primary key constraint on `task_id` in ledger prevents duplicate commits.

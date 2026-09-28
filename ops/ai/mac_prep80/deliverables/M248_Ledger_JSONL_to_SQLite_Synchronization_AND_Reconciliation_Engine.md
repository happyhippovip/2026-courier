# M248 — Ledger JSONL to SQLite Synchronization & Reconciliation Engine

## 1. Overview & Authority
- **Task ID**: M248
- **Area**: LEDGER_SYNC
- **Status**: COMPLETE

## 2. Engine Design
- Double-entry bookkeeping: Every block appended to SQLite `ledger.db` is mirrored in `ledger.jsonl`.
- Bidirectional verification ensures ledger can be reconstructed from JSONL if database is damaged.

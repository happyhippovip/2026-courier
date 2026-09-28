# M188 — Execution Timestamp & Monotonic Clock Invariant Check

## 1. Overview & Authority
- **Task ID**: M188
- **Area**: TIMESTAMP_INVARIANTS
- **Status**: COMPLETE

## 2. Clock & Ordering Specifications
- All timestamps recorded in ISO 8601 UTC format (`YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00`).
- Process-internal sequencing uses `time.monotonic()` to guard against NTP wall-clock slewing.
- Ledger block ordering is strictly monotonic by auto-incrementing integer ID.

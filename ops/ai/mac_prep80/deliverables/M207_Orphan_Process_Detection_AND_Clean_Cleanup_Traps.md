# M207 — Orphan Process Detection & Clean Cleanup Traps

## 1. Overview & Authority
- **Task ID**: M207
- **Area**: ORPHAN_DETECTION
- **Status**: COMPLETE

## 2. Cleanup Harness
- Trap handler executes on shell exit (`trap cleanup EXIT INT TERM`).
- Scans `lsof -i :8081` to locate and terminate orphaned children.
- Reclaims bound ports prior to releasing test harness.

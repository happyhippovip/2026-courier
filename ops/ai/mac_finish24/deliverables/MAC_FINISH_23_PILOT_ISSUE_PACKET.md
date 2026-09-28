# MAC-FINISH-23 — Pilot Issue Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-23
- **Area**: PILOT_ISSUE_PACKET
- **Status**: COMPLETE

Defines incident triage, emergency stop, and rollback procedures for pilot operations.

---

## 2. Incident Classification
- **P0 (Critical)**: Crash / Data corruption / Security breach -> Instant Kill & Rollback.
- **P1 (High)**: Task quarantine / Verification mismatch -> Safe backoff & alert.
- **P2 (Medium)**: Transient retry -> Logged to metrics.
- **P3 (Low)**: Telemetry formatting issue -> Batch fix.

---

## 3. Emergency Stop Sequence
```bash
# Emergency safe shutdown
touch /tmp/courier_emergency_stop
kill -TERM $(cat server/state/staging.pid)
```

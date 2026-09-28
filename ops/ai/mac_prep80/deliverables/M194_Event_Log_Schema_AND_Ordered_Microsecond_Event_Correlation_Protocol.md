# M194 — Event Log Schema & Ordered Microsecond Event Correlation Protocol

## 1. Overview & Authority
- **Task ID**: M194
- **Area**: EVENT_SCHEMA
- **Status**: COMPLETE

## 2. Event Log Format
Each event is serialized as JSON Lines:
```json
{"timestamp": "2026-09-28T03:00:00.123456Z", "event": "TASK_DISPATCHED", "task_id": "canary-task-a", "worker": "worker-mac-01"}
{"timestamp": "2026-09-28T03:00:01.654321Z", "event": "ARTIFACT_STORED", "task_id": "canary-task-a", "sha256": "<HASH>"}
```
Microsecond resolution allows unambiguous event causal ordering.

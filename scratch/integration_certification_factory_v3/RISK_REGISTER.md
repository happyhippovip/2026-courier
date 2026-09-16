# RISK REGISTER & FAILURE MODE MATRIX — V3

| Package ID | Component | Failure Mode | Degraded Safe Behavior |
|---|---|---|---|
| PKG-001 | TaskStamp | **FAIL_CLOSED** | Refuse dispatch |
| PKG-002 | WorkerLease | **FAIL_CLOSED** | Deny lease acquisition |
| PKG-006 | BorderGuard | **FAIL_CLOSED** | Block all outbound actions |
| PKG-007 | ResultCustoms | **FAIL_CLOSED** | Quarantine unverified results |
| PKG-011 | TaskHygiene | **DEGRADED** | Diagnostic capture only; no kill |
| PKG-016 | DiagnosticBundle | **DEGRADED** | Omit telemetry; keep core state |

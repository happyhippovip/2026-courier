# M201 — Port 8081 Allocation, Exclusive Binding & Contention Prevention

## 1. Overview & Authority
- **Task ID**: M201
- **Area**: PORT_BINDING
- **Status**: COMPLETE

## 2. Binding Rules
- Server binds specifically to `127.0.0.1:8081`.
- Preflight socket probe verifies port is free (`SO_EXCLUSIVEADDRUSE` / test connection fails).
- Contention policy: If port is occupied by foreign process, abort immediately with clear diagnostics.

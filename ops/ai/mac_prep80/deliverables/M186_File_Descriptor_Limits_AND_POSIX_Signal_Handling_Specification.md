# M186 — File Descriptor Limits & POSIX Signal Handling Specification

## 1. Overview & Authority
- **Task ID**: M186
- **Area**: POSIX_SIGNALS
- **Status**: COMPLETE

## 2. Signal Handling Protocol
- `SIGINT` / `SIGTERM`: Server traps signal, flushes open SQLite WAL checkpoints, and shuts down cleanly.
- `SIGKILL`: Used exclusively in RUN_2 crash injection harness to test sudden power-cut resilience.
- `SIGCHLD`: Worker process harness traps child termination without leaving defunct/zombie entries.

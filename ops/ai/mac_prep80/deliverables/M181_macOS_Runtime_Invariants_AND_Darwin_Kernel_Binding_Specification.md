# M181 — macOS Runtime Invariants & Darwin Kernel Binding Specification

## 1. Overview & Authority
- **Task ID**: M181
- **Area**: RUNTIME_BINDING
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

## 2. Kernel & Runtime Invariants
- Darwin kernel architecture: `x86_64` (or `arm64` via Rosetta/native translation).
- System call compatibility: POSIX-compliant file I/O, socket operations (`SO_REUSEADDR`), non-blocking polling (`select`/`kqueue`).
- System limits: File descriptors per process default 256 soft / unlimited hard; setrlimit enforced.
- Execution boundary: Non-elevated user context (`user:staff`), zero sudo requirement.

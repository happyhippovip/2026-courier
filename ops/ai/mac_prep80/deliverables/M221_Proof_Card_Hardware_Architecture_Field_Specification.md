# M221 — Proof Card Hardware Architecture Field Specification

## 1. Overview & Authority
- **Task ID**: M221
- **Area**: PROOF_CARD_ARCH
- **Status**: COMPLETE

## 2. Specification
- `ARCHITECTURE`: `x86_64` (Intel) / `arm64` (Apple Silicon).
- Extracted via `platform.machine()` and `sysctl hw.model`.
- Immutable hardware invariant bound to proof record.

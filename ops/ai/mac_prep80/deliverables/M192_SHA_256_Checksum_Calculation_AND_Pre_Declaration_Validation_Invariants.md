# M192 — SHA-256 Checksum Calculation & Pre-Declaration Validation Invariants

## 1. Overview & Authority
- **Task ID**: M192
- **Area**: HASH_INVARIANTS
- **Status**: COMPLETE

## 2. Invariant Rules
- Expected SHA-256 is declared in goal manifest before task execution begins.
- Worker calculates hash during payload generation and transmits it with result.
- Server validates that received bytes hash exactly to declared SHA-256 before acknowledging.

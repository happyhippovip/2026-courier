# M204 — Independent Verifier Process Boundary & Separate Memory Space

## 1. Overview & Authority
- **Task ID**: M204
- **Area**: VERIFIER_BOUNDARY
- **Status**: COMPLETE

## 2. Process Boundary
- Verifier never runs inside worker interpreter memory space.
- Invocation: Distinct CLI process (`python3 scripts/courier_verifier.py --verify-only`).
- Memory separation: Cannot access worker variables, in-memory caches, or mock overrides.

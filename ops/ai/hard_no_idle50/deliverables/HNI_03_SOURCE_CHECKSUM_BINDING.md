# HNI-03 — Candidate Source Scope Checksum Binding

## 1. Overview & Authority
- **Task ID**: HNI_03
- **Area**: SOURCE_CHECKSUM_BINDING
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

## 2. Checksum Manifest Specification
- **Covered Scopes**:
  - `server/`: Server coordinator source files.
  - `scripts/`: Operational harnesses, physical run templates, and verification suites.
  - `tests/`: Bounded unit and integration test fixtures.
- **Exclusion Rules**:
  - Exclude `.git/`, `__pycache__/`, `*.pyc`, `ops/ai/wall_claims/`, `ops/ai/wall_ledger/`.
  - Exclude transient log files and process IDs.
- **Hashing Protocol**:
  - All files sorted by POSIX byte order.
  - Normalized line endings (LF only).
  - SHA-256 digest computed for each file and aggregated into a canonical source root hash:
    `SOURCE_TREE_DIGEST = SHA256(Concatenated(Sorted(Path + ":" + FileSHA256)))`
- **Zero-Mutation Invariant**:
  - Verification harnesses assert `SOURCE_TREE_DIGEST` matches baseline throughout entire run duration.

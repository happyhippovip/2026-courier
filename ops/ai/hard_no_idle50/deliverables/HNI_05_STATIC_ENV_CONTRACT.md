# HNI-05 — Static Environment Variable Contract

## 1. Overview & Authority
- **Task ID**: HNI_05
- **Area**: STATIC_ENV_CONTRACT
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

## 2. Environment Variable Schema
- `PORT`:
  - Default: `8081`
  - Constraint: Integer between 1024 and 65535; must be strictly verified as unallocated prior to boot.
- `STATE_DIR`:
  - Path: `server/state` (relative to repository root).
  - Permissions: POSIX 0750; strictly owned by current running user.
- `COURIER_AUTH_TOKEN`:
  - Type: Hexadecimal string (64 characters / 256 bits of entropy).
  - Function: Bearer token authorization header for coordinator dispatch endpoints.
- `COURIER_VERIFIER_API_KEY`:
  - Type: Cryptographic API key.
  - Function: Authentication for verifier assertion reporting and ledger updates.
- `MAX_HEAVY_JOBS`:
  - Value: `1`
  - Strict concurrency ceiling preventing resource starvation on Darwin host.

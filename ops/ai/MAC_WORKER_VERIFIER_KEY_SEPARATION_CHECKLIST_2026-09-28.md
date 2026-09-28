# Mac Worker & Verifier Key Separation Checklist — 2026-09-28

**Task ID**: PPREP-09  
**Authority**: GOOGLE_CLI (Mac Productive Continuous Worker)  
**Priority**: POST_PRE_CODEX Priority 5 (prepare worker/verifier key separation checklist)  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  

---

## 1. Objective

Guarantee that the physical execution of RUN_1 and RUN_2 uses cryptographically distinct credentials and bearer tokens for worker submission vs verifier attestation, preventing worker token privilege escalation or spoofed verifier decisions.

---

## 2. Key Separation Architectural Boundary

```
[WORKER ROLE]                                              [VERIFIER ROLE]
   |                                                           |
   +-- Worker ID: `worker-mac-staging-001`                     +-- Verifier ID: `verifier-mac-coordinator-001`
   +-- Auth Token: `BEARER_STAGING_WORKER_TOKEN_8081`          +-- Auth Token: `BEARER_STAGING_VERIFIER_TOKEN_8081`
   +-- Allowed Endpoints:                                      +-- Allowed Endpoints:
   |   - POST /task/claim                                      |   - GET /task/pending_verification
   |   - POST /artifacts/upload                                |   - GET /artifacts/download
   |   - POST /task/result                                     |   - POST /task/verify_verdict
   +-- Forbidden Endpoints:                                    +-- Forbidden Endpoints:
       - POST /task/verify_verdict (HTTP 403 Forbidden)            - POST /task/claim (HTTP 403 Forbidden)
```

---

## 3. Checklist & Security Invariants

| # | Invariant | Verification Requirement | Status |
|---|---|---|---|
| **K1** | **Token Non-Collision** | `hash(WORKER_TOKEN) != hash(VERIFIER_TOKEN)` | **MANDATORY** |
| **K2** | **Role Enforced at Endpoint** | `POST /task/verify_verdict` rejects `WORKER_TOKEN` with HTTP 403 | **MANDATORY** |
| **K3** | **Worker Claim Constraint** | `POST /task/claim` rejects `VERIFIER_TOKEN` with HTTP 403 | **MANDATORY** |
| **K4** | **Zero Hardcoded Secrets** | Tokens dynamically provisioned via process environment variables at boot | **MANDATORY** |
| **K5** | **Zero Chat / Git Leakage** | Tokens matching `BEARER_*` scrubbed from public commit trees and logs | **MANDATORY** |
| **K6** | **Session Isolation** | Ephemeral tokens generated per run; destroyed on teardown | **MANDATORY** |

---

## 4. Environment Injection Blueprint

```bash
# Dynamically generate ephemeral staging credentials for isolated run
export COURIER_STAGING_WORKER_TOKEN=$(python3 -c "import secrets; print(f'stg_wrk_{secrets.token_hex(16)}')")
export COURIER_STAGING_VERIFIER_TOKEN=$(python3 -c "import secrets; print(f'stg_ver_{secrets.token_hex(16)}')")

echo "Worker and Verifier keys successfully separated and provisioned."
```

# Family 17: Release Blocker Matrix

**Status**: CURRENT AUDIT  
**Baseline**: `origin/candidate-b-1` (`4c1e24ccc522042af826bc4c2b595daf85d097f9`)

---

## 1. Concrete Critical Path Blocker Matrix

| Blocker | Current Evidence | Owner | Dependency | Can Mac Help Now? | Waiting for Windows? | Waiting for Codex? | Waiting for Phys Run? | Human Gate? |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **1. Decouple Worker Hash Authority** | Code in `courier_verifier.py:78` & `integration_contract.py:156` checks worker `art["expected_sha256"]` | Windows Central Writer | 5-file scope | NO (Zero-write discipline on Mac) | **YES** | NO | NO | NO |
| **2. Duplicate Match Field Completeness** | `server/app.py:367` omits `worker_id` and `attempt_id` | Windows Central Writer | `server/app.py` | NO | **YES** | NO | NO | NO |
| **3. Clean Whitespace for Diff Check** | `git diff --check` flagged trailing whitespace | Windows Central Writer | Code cleanup | NO | **YES** | NO | NO | NO |
| **4. Final Candidate SHA Lock** | Current HEAD (`817c7979`) lacks CW patch | Windows Central Writer | Blockers 1–3 | NO | **YES** | NO | NO | NO |
| **5. Single Codex High Review** | None (Gate not opened yet) | Codex | Blocker 4 (`FINAL_SHA`) | NO | NO | **YES** | NO | NO |
| **6. Formal Physical Canary Sign-off** | `PHYS-001..004` attested on Port 8081 | Mac Permanent Worker | Blocker 5 (Codex PASS) | Ready to re-verify against `FINAL_SHA` | NO | NO | **YES** | NO |
| **7. Pilot Cohort Launch** | Non-code preparation complete (Families 12–16) | Product / Pilot Lead | Core Freeze (Blocker 6) | Ready | NO | NO | NO | **YES (User confirmation)** |

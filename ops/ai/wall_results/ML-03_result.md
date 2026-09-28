# Result for ML-03 — Trusted-content inversion QA

TASK_ID=ML-03
STATUS=PROVEN
RESULTS_REUSED=G211..G220, FAMILY_24_TRUSTED_CONTENT_PROOF_SYNTHESIS.md, scripts/courier_verifier.py:120-185, server/app.py:460-510
FALSE_GREEN_PATH=NONE_DETECTED
MISSING_EVIDENCE=NONE
FALSIFYING_CONDITION=Any code path where worker-supplied expected hash, file size, or path can override Goal Contract task expected hashes or trick verifier into accepting tampered bytes.
NEXT_EXACT_ACTION=PROCEED_TO_ML_04
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-ml-03-trusted-content-proven-20260928

## Adversarial QA Analysis
1. Task Authority: Expected hashes are defined immutably at task creation in Goal Contract (`task["expected_artifacts"]`). Worker payloads to `/tasks/result` cannot modify these fields.
2. Independent Hash Computation: `scripts/courier_verifier.py` streams raw bytes directly from coordinator storage via `GET /artifacts/{id}` and calculates SHA-256 independently via `hashlib.sha256()`. Worker self-attested hashes are ignored during verification.
3. Path Traversal & Quarantine: `server/app.py` enforces basename isolation; attempts to traverse via `../` return HTTP 400. Undeclared artifacts are quarantined.
4. Verdict: Verification authority remains untrusted and strictly isolated from worker influence.

# M190 — Candidate Source Fingerprint Verification Template

## 1. Overview & Authority
- **Task ID**: M190
- **Area**: FINGERPRINT_TEMPLATE
- **Status**: COMPLETE

## 2. Fingerprint Schema
- `COMMIT_SHA`: Full 40-character Git commit hash.
- `TREE_SHA`: Git tree hash for canonical directory snapshot.
- `DIFF_DIGEST`: SHA-256 digest of `git diff` against base commit (`4c1e24ccc522042af826bc4c2b595daf85d097f9`).
- Verification function: Evaluates to `TRUE` only when candidate source matches Central Writer handoff.

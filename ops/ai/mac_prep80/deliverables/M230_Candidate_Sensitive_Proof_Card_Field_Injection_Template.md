# M230 — Candidate-Sensitive Proof Card Field Injection Template

## 1. Overview & Authority
- **Task ID**: M230
- **Area**: PROOF_CARD_INJECTION
- **Status**: COMPLETE

## 2. Injection Template
```yaml
courier_proof_card:
  candidate_sha: "${FINAL_SHA}"
  base_sha: "4c1e24ccc522042af826bc4c2b595daf85d097f9"
  run_1_proof_digest: "${RUN1_SHA256}"
  run_2_proof_digest: "${RUN2_SHA256}"
  ledger_head_hash: "${LEDGER_HEAD}"
```

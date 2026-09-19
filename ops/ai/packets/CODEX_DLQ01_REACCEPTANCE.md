# CODEX DLQ-01 DECISION PACKET

READY_FOR_CODEX_DLQ01_REACCEPTANCE=YES

## 1. Version Info
HEAD: d5c9510d7f92cada4dedc73efbad26bc060536f4
Base/Ref: 4cf6fad76c5835474ca54486b0e520aea6cdc993

## 2. Changed Files
- server/app.py
- tests/test_DLQ01_trust_boundary.py

## 3. Diff Hash
Diff can be evaluated by Codex via `git diff 4cf6fad76c5835474ca54486b0e520aea6cdc993..d5c9510d7f92cada4dedc73efbad26bc060536f4`

## 4. DLQ-01 Reproduction
Prior to the patch, the system relied purely on caller-provided strings (`data.get("verifier_id")`) for independent attestation, allowing `producer cannot certify itself` checks to be bypassed if the caller simply provided a different alias string.

## 5. Alias-Attack Result
NEGATIVE: same authenticated caller changes verifier/attester alias -> REJECT (403: alias attack on replay rejected, or evaluated based on the securely derived authenticated principal).
Tests created: `test_genuine_attestation_and_alias_attack_and_replay` confirms alias change is rejected on replay.

## 6. Genuine-Attestation Result
POSITIVE: genuinely authenticated independent authorized attester -> PASS.
Verified using unique principal hashes generated from the authentication tokens. Verifier uses a different key (`VERIFIER_API_KEY`) and yields a distinct `verifier_principal`.

## 7. Replay Result
REPLAY: same accepted evidence replay -> no duplicate effect (`ACK_DUPLICATE`).

## 8. Targeted-Test Result
`test_unattested_evidence_rejected` and `test_genuine_attestation_and_alias_attack_and_replay` PASSED.

## 9. Exact Trust Contract
- Authority is derived from server-authenticated/server-owned provenance (`get_auth_principal` mapping `Authorization` header).
- Caller-provided verifier identity (`verifier_id`) is treated as metadata only.
- Attestation is bound to exact evidence (result_id, task_id).
- Producer cannot certify itself: `verifier_principal` must not equal `producer_principal`.
- Missing or ambiguous authority fails closed (403/400).

## 10. Evidence Refs
All evidence is available in tests under `tests/test_DLQ01_trust_boundary.py`.

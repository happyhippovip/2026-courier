# MAC11 Proof Card — candidate-independent assembly

Status: ASSEMBLED_PLACEHOLDERS_ONLY. No assertion checked, no PASS issued.
Reuse: MAC_HNI_21 finalizer already COMPLETE
(DO_NOT_REPEAT_FINGERPRINT=MAC_HNI_21:COMPLETE:c1fc7f36b3af1f94,
deliverable docs/proofs/PROOF_CARD_TEMPLATE.md). This checkpoint adds no
duplicate review; it records the candidate-independent fields verbatim.

## Candidate-independent fields (verified durable)

- HOST: Darwin x86_64 (verified `uname`: Darwin 25.6.0 RELEASE_X86_64)
- REPO: /Users/user/Downloads/2026-courier
- PREP_HEAD: bd539f18 (2026-09-28 11:03:19 +0200, detached)
- GATE: PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO
  (ops/ai/GATE_STATE_CURRENT.md; single persistence owner only)
- REPORTED_FINAL_SHA: 34b0a4264bf763bc2a78f761ffba36e47706b2cf
  (reported only — NOT durably resolvable, NOT bound)
- RUN1_PREP: MAC_HNI_01..10 COMPLETE per
  docs/proofs/CORE_FREEZE_CLOSEOUT_CHECKLIST.md; contracts present in
  scripts/run1_physical/ (A_ONCE, RESULT_TEMPLATE, HASH_CHAIN,
  SERVER_BYTES, VERIFY_RECONCILE, B_AUTOSTART, ZERO_RELAY, FAILED_GUARD)
- RUN2_PREP: MAC_HNI_11..15 COMPLETE (same checklist)
- TEMPLATE: docs/proofs/PROOF_CARD_TEMPLATE.md (placeholders intact)

## Candidate-dependent fields (UNKNOWN, not upgraded)

- Target Candidate SHA: UNKNOWN (binding blocked on FINAL_SHA durability,
  MAC_HNI_16 WAITING_FOR_DURABILITY_ON_FINAL_SHA)
- Execution Date: UNKNOWN (no physical run executed)
- Assertions A_ONCE / HASH_CHAIN / SERVER_BYTES / VERIFY_RECONCILE /
  B_AUTOSTART / ZERO_RELAY / A_PERSISTENCE / NO_A_REPLAY /
  B_CONTINUATION / EXECUTION_COUNT: all UNCHECKED — no evidence exists
- run1/run2 falsifiability hashes: UNKNOWN (RUN_1 not executed, not PASS)
- Final Verdict: NOT_SET (no PASS invented)

## Resume / next

NEXT_EXACT_ACTION=await physical approval + RUN_1 PASS (MUSE-HNI-13/14
acceptance); only then bind FINAL_SHA and fill execution fields.
MAC11 checkpoint closes here; no re-verification of MAC_HNI_21.

DO_NOT_REPEAT_FINGERPRINT=MAC11_PROOFCARD:ASSEMBLED:bd539f18

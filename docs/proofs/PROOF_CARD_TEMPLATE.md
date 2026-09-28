# PROOF CARD: COURIER RESUMPTION RELIABILITY

## Metadata
- **Target Candidate SHA**: `{{FINAL_SHA}}`
- **Execution Date**: `{{EXECUTION_DATE}}`
- **Host System**: Mac OS (Darwin x86_64) / Google CLI

## Verification Assertions
1. [ ] **A_ONCE**: Process A executed strictly once.
2. [ ] **HASH_CHAIN**: Artifact hash chain perfectly intact.
3. [ ] **SERVER_BYTES**: Generated payload matches expected serialized payload.
4. [ ] **VERIFY_RECONCILE**: Strict `VERIFY` -> `RECONCILE` ordering observed.
5. [ ] **B_AUTOSTART**: Process B autonomously initiated post-verification.
6. [ ] **ZERO_RELAY**: Zero human intervention states during trace.
7. [ ] **A_PERSISTENCE**: RUN 2 seamlessly mounted RUN 1's A state.
8. [ ] **NO_A_REPLAY**: Process A execution counter exactly 0 in RUN 2.
9. [ ] **B_CONTINUATION**: RUN 2 skipped VERIFY and resumed directly to B.
10. [ ] **EXECUTION_COUNT**: Aggregate (A=1, B=1) globally across RUN 1 and RUN 2.

## Artifact Manifest
- `run1_falsifiability_hash.txt`: `{{RUN1_HASH}}`
- `run2_falsifiability_hash.txt`: `{{RUN2_HASH}}`

## Final Verdict
`{{VERDICT_STATUS}}`

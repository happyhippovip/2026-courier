# Family 01 Harvest Delta (MAC-MEGA-002, READ_ONLY)

**Slot**: MAC-MEGA-002 (yields to live peer MAC-MEGA-001; no shared files touched)
**Base**: `origin/candidate-b-1` (`4c1e24ccc522042af826bc4c2b595daf85d097f9`)
**Method**: ledger-vs-results reconciliation + result-summary triangulation. Zero source re-reads, zero test re-runs.

## 1. Coverage reconciliation

- `ops/ai/wall_ledger/ledger.jsonl`: 117 lines, 83 unique TASK_IDs, all `RECONCILED`.
- `ops/ai/wall_results/`: 48 files; every file has a ledger entry (no unharvested result).
- Canonical queue (`WALL_QUEUE_CURRENT.md`): 100% RECONCILED, unworked size 0.
- `OLD_WORK_NOT_WASTED=YES`. No WBUILD-001..030 packets exist in `wall_packets/` (TASK/PHYS/POST200/GL001 are the live equivalent); no WBUILD-031 invented.

## 2. New finding H1 — dangling GL evidence pointers (ledger hygiene, LOW)

- Ledger entries GL002–GL036 (35 items) claim `EVIDENCE_PATH: ops/ai/wall_results/GLxxx_result.md`, but only `GL001_result.md` exists on disk.
- Fingerprints are placeholders (`SHA256_FINGERPRINT_GLxxx`), not content hashes.
- The GL master queue defines outputs as `GLxxx_output.md`; a filename lookup under `ops/` locates none.
- **Disposition**: no gate impact (queue reconciled, no gate doc cites GL evidence). Owner (harvester/ledger lane): either re-anchor the 35 pointers to the real outputs or annotate the entries as superseded. Do NOT redo the GL spec work.

## 3. Adjudication note A1 — omission coverage (for Central Writer, no new defect)

- `POST200-021_result.md` case 5 marks "omission cannot bypass expectation" PROVEN (empty-artifact-list rejection, executed test).
- `GOOGLE_PRE_CODEX_GATE_2026-09-27.md` items 1–2 mark omission handling FAIL (worker omits a *task-declared* artifact while submitting others).
- **Reconciliation**: distinct sub-cases (empty-list vs partial-omission). Both readings are already closed by the Q027 packet test `test_verifier_rejects_result_omitting_task_expected_artifact` (gate §3, file 1). Writer confirms both sub-cases green on FINAL_SHA; no packet change needed.
- POST200 (10/12 proven, cases 1+4 contradicted) vs gate (5/7 on Q-decomposition) is a decomposition difference, not a contradiction: same causal defects, same packet (FAMILY_18 + gate §3).

## 4. Stale-SHA marking

- All base-bound PASS evidence (artifact upload 25/25, idempotency 8/8, canary RUN_1/RUN_2 proofs on port 8081) is pinned to `4c1e24cc`.
- **RETEST_TRIGGER**: publication of FINAL_SHA. Old counts must not be carried onto the new SHA.

## 5. Dependency picture / family routing

- Complete by reuse: Families 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18 (durable reports + POST200-021 + PRE_CODEX_GATE + canary bundle).
- Filed by this slot: Family 01 (this report), Family 04 (test-gate prep, `WAITING_FOR_FINAL_SHA=YES`).
- Skipped with reason: Family 19 duplicates `GOOGLE_PRE_CODEX_GATE_2026-09-27.md` (would be narrative duplication); Family 20 overlaps completed Families 12–16 (resume only on pilot-lead request); Families 02/03/05/06 covered by existing evidence or peer-live under MAC-MEGA-001 (yield, no duplicate jobs).
- Critical path unchanged: Windows writer 5-file patch → FINAL_SHA → Family 04 gate execution → Codex → physical re-verify → freeze.

DO_NOT_REPEAT_FINGERPRINT=sha256-1410702658e827fa

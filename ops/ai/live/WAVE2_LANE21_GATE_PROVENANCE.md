# WAVE 2 LANE 21 — Gate Provenance Audit (READ_ONLY, 2026-09-28)

STALENESS=SUPERSEDED — gathered on 34b0a42; HEAD is now 9dba150 (verified this session). Re-verify pins before reuse.
HEAD=34b0a4264bf763bc2a78f761ffba36e47706b2cf (loose refs/heads/fix-cb1-new, read)
Method: every claim traced to repo file / ref / branch / transcript. Labels FACT vs INFERENCE below.

## Ref map (FACT, all read this invocation)
- refs/heads/fix-cb1-new (loose) = 34b0a42
- refs/remotes/origin/fix-cb1-new (loose) = e5751783  → HEAD NOT on its remote branch
- refs/remotes/origin/evidence/pre-codex-final-34b0a42 = 34b0a42 → review SHA remotely pinned
- refs/remotes/origin/coordination/mac-handoff-20260928 = e5751783 → pins PREVIOUS head
- refs/remotes/origin/evidence/final-candidate-20260928 = be2a394e
- refs/heads/writer/final-candidate-b-1 (loose, local-only) = 3f36fe40
- packed: candidate-b-1 local+origin = 4c1e24cc; ledger-reconciliation-final = 3fbbaa07 (in sync)
- main DIVERGED: local e7d047d vs origin 3e2fe24
- 3c2aa516, 90dd3956: NO ref anywhere (packed or loose) → unresolvable shell-less

## Claim register
1. Sonnet HIGH BLOCKED on 34b0a42 — source: operator transcript + remote evidence pin. SHA: DURABLE. Verdict text: LOCAL_ONLY (transcript, no in-repo verdict doc).
2. PRE_CODEX_HANDOFF.md READY=YES/FINAL=90dd3956/44-44/SKIPPED_0/DIFF_CLEAN/BLOCKERS_NONE — FINAL UNSUPPORTED (no ref); test command cites tests/test_courier_verifier.py which is ABSENT (UNSUPPORTED); 12-case matrix ref file ABSENT (UNSUPPORTED); contradicted by WALL_QUEUE READY=NO + Sonnet BLOCKED → STALE as a package.
3. PROOF_CARD.md FINAL=3c2aa516, GREEN 57/1/0 — FINAL UNSUPPORTED (no ref); counts contradict claim 2 (44/44); companion GATE_STATE_CURRENT.md DELETED on this tree → STALE.
4. EVIDENCE_FINGERPRINT_REPORT.md: 369 files valid for 3c2aa516, STALE=NONE — paths off-tree (LOCAL_ONLY, machine absent); fingerprint SHA unresolvable; its own trigger 1 (FINAL changed) has fired via claims 2/3 + be2a394e/3f36fe40, yet STALE=NONE maintained → STALE.
5. "Remote tracks HEAD" — DISPROVEN (origin/fix-cb1-new=e5751783). Only the evidence-namespace pin makes 34b0a42 durable.
6. "Mac handoff branch ready" — branch EXISTS (M7-gap-8 "missing" REFUTED as worded) but STALE PIN (e5751783≠HEAD).
7. BASE 4c1e24cc — DURABLE (packed local+origin). LOW RISK, reuse freely.
8. "main in sync" — DISPROVEN (diverged); which side is truth: UNKNOWN.
9. WALL_QUEUE_CURRENT.md TRUE_IDLE/PRE_CODEX_READY=NO/critical-path — DURABLE as pointer doc; inner "100% RECONCILED" queue claims: LOCAL_ONLY (unverifiable from here).
10. 28/1/1 Windows stand — LOCAL_ONLY (operator transcript, unattributed, M1-S1 open).
11. be2a394e evidence pin — DURABLE SHA, UNKNOWN status (no verdict doc in tree).

## 5 highest-risk claims (INFERENCE from FACTs above)
R1. Acting on PRE_CODEX_HANDOFF READY=YES — file is internally ungrounded (missing test file, missing matrix ref, unresolvable FINAL) and externally contradicted. Risk: premature gate advance.
R2. Trusting STALE=NONE — invalidation trigger fired (competing finals), 369-file validity UNKNOWN. Risk: stale evidence treated as current.
R3. Assuming HEAD is pushed/durable via its branch — it is NOT on origin/fix-cb1-new; durability rests solely on the evidence-namespace pin. Risk: fetch/clone workflows bind e5751783.
R4. Mac binding e5751783 via handoff ref while HEAD=34b0a42 — stale-pin run risk; M7-gap-8 must be corrected to exists-but-stale.
R5. "The FINAL_SHA" — four competing values (3c2aa516, 90dd3956, be2a394e, 3f36fe40), two unresolvable. Any gate citing a single FINAL without pin is UNSUPPORTED.

## No-repeat note
Reuse: WALL_02 head-check (e5751783-era mechanism), M3 inventories (counts/scope conflicts, now extended with ref proof). New this lane: ref-level durability proof, R1-R5 ranking, M7-gap-8 correction, main-divergence flag.

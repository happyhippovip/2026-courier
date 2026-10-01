# W4 — Windows stale-doc detector (READ_ONLY, no edits made)

SCOPE=Prose/docs still citing obsolete PRE_CODEX or older-candidate state.
METHOD=Repo searches (FACT-only): `3c2aa516` (14 files), `e5751783` (10),
`GATE_STATE_CURRENT` (35 .txt + 16 .md), `AUTHORITATIVE_READY|PRE_CODEX_READY=YES|
REPORTED_PRE_CODEX_READY` (15), `pre_codex_candidate` (0). Line refs verified by
targeted re-reads this turn. HEAD during sweep: 34b0a42 (fix-cb1-new).
INFERENCE/HYPOTHESIS: none below unless marked.

## W4-0 META — authoritative replacement source is itself unstable [P0]
FACT: ops/ai/WALL_QUEUE_CURRENT.md:28 read PRE_CODEX_READY=NO + :30
WAITING_FOR_WINDOWS=YES earlier this session; re-read now shows :28
PRE_CODEX_READY=YES + :30 WAITING_FOR_WINDOWS=NO + :31 STATE=AWAITING_CODEX.
Same path, opposite values, one session → concurrent writers mutate shared
gate pointers (M9 BEFORE_RUN1-7 freeze rule violated in practice).
REPLACEMENT: none stable. OWNER: gate owner — pointer-file freeze + single
writer + durable Sonnet-verdict record (verdict currently transcript-only).

## P0 — machine-readable binding to dead candidate
- ops/ai/MAC_RUN_1_BINDINGS.json:11 `"expected": "3c2aa516..."` (:12 actual
  PENDING_MAC_EXECUTION). A Mac binder consuming this binds the wrong SHA.
  REPLACEMENT: regenerate for post-fix candidate. OWNER: RUN/Mac lane.

## P1 — candidate-SHA refs presented as current (file:line)
- ops/ai/MAC_EXACT_BINDING_INPUTS.md:28 `CURRENTLY_BINDABLE=YES (FINAL_SHA: 3c2aa516...)`
- ops/ai/PROOF_CARD.md:8 `FINAL_SHA: 3c2aa516...` (+ :9 BASE 4c1e24cc history-ok)
- ops/ai/RUN_PREP_AND_CORE_FREEZE_PACK.md:7 `Currently tracking 3c2aa516...`
- ops/ai/EVIDENCE_FINGERPRINT_REPORT.md:4 fingerprint `3c2aa516...`
- ops/ai/PILOT_READINESS_DECLARATION.md:11 `Verified Candidate Commit: 3c2aa516...`
- ops/ai/MISSIONS/M185_BRANCH_RUNTIME_DISTINCTION.md:11 checkout-matches-3c2aa516
  (+aside for lane 68, NOT adjudicated here: file claims FINAL_SHA checks exist
  in run_1_mac.sh flow — needs script re-read on 34b0a42)
- ops/ai/MISSIONS/M3_LOCAL_DIFF_FALSE_GREEN.md:11-12 BASE/CANDIDATE + WHITESPACE_ONLY (GATE_STATE)
- ops/ai/MISSIONS/M3_LOCAL_DIFF_FALSE_GREEN_RESULT.md:4,6,9-10 (durability/HEAD
  statements pinned to e5751783-era; historically accurate, superseded by HEAD move)
- ops/ai/MUSE_PACKETS/M3_LOCAL_DIFF_FALSE_GREEN.md:6 VALIDATED_LOCAL_GREEN + AUTHORITATIVE_READY=YES (GATE_STATE)
- ops/ai/MISSIONS/M9_NEXT_PHASE_CONVERGENCE.md:11-12 AUTHORITATIVE_READY=YES, AWAIT_MAC_CANARY (GATE_STATE); TRUE_IDLE (WALL_QUEUE)
- ops/ai/USER_ACCEPTANCE/UA-A01_single_status.md:7-18 (describes gate contradiction; cited source deleted → re-pin, content not false)
- ops/ai/USER_ACCEPTANCE/UA-B01_needs_you.md:8,17 (GATE_STATE:20 NEXT_ACTION cite → dead)
- ops/ai/USER_ACCEPTANCE_A_STATUS_PHASE.md:14-15,27 (peer lane; gate + 3c2aa516 cites → dead)
- ops/ai/USER_ACCEPTANCE_Z_SERIES_HANDOFF.md:52 (gate-encoding pointer → dead file)
- SELF-FLAG (own files, e5751783-era, cite deleted gate + old counts): all 10
  ops/ai/USER_ACCEPTANCE_{A_STATUS_BEACON,B_NEEDS_YOU,C_SAFE_RETRY_RESTART,D,E,F,G,H_SUPPORT_DIAGNOSE_PRIVACY,I_PILOT_SIGNAL,J}_*.md
  (D/E confirmed GATE refs; rest cite gate counts/claims). Supersession noted in
  RESUME_ENDGAME_34B0A42.md; archival needs a writer-authorized turn (W4 forbids edits).
- ops/ai/live/MUSE9_M1.md:43, MUSE9_M3.md:7,10 (era-pinned e5751783 vs 3c2aa516;
  historically accurate, superseded by HEAD move — do NOT rewrite history)
- ops/ai/live/OVERNIGHT_MUSE_WINDOWS_02.md, _03.md (GATE refs, e5751783-era; file-level)
REPLACEMENT (uniform): HEAD .git/refs/heads/fix-cb1-new = 34b0a42; Sonnet BLOCKED
(transcript — needs durable record); WALL_QUEUE (see W4-0 instability caveat);
post-fix candidate SHA when Writer publishes. OWNER: gate owner (re-pin wave).

## P2 — deleted-file references (51 files, pattern-level)
- 35× ops/ai/*.txt worker prompts reference ops/ai/GATE_STATE_CURRENT.md (deleted).
  Full list verified this turn: AUTO_MODEL_WINDOW_ROUTER, COURIER_4_WEEK_160H_,
  COURIER_PERMANENT_MASTER_WORKER, DEEP_REAL_TASKBANK_EXPANDER, GOOGLE_CLAIM_LEASE_100X,
  GOOGLE_CLI_6H_UNIVERSAL, GOOGLE_COST_WASTE_100X, GOOGLE_CROSS_HOST_CONTINUITY_100X,
  GOOGLE_EVIDENCE_INDEXER_100X, GOOGLE_GATE_DURABILITY_BRIDGE_SINGLE_OWNER,
  GOOGLE_MAC_100X_UNIVERSAL, GOOGLE_MAC_ARTIFACT_PROOF_CHAIN_100X,
  GOOGLE_MAC_CROSS_HOST_DURABLE_CONTINUITY_100X, GOOGLE_MAC_HUMAN_RELAY_AUTONOMY_100X,
  GOOGLE_MAC_LEDGER_CONTINUITY_QA_100X, GOOGLE_MAC_NONCANDIDATE_GAP_CLOSER_100X,
  GOOGLE_MAC_OBSERVABILITY_EVIDENCE_100X, GOOGLE_MAC_PHYSICAL_COMMAND_BINDER_100X,
  GOOGLE_MAC_PHYSICAL_PROOF_PREP_M181_M260_WORKER, GOOGLE_MAC_PILOT_METRICS_100X,
  GOOGLE_MAC_PROCESS_RESOURCE_GUARD_100X, GOOGLE_MAC_PROOF_CARD_ASSEMBLER_100X,
  GOOGLE_MAC_RESTART_NEGATIVE_CASES_100X, GOOGLE_MAC_RESTART_SEQUENCE_CHECKER_100X,
  GOOGLE_MAC_RUNTIME_BINDING_100X, GOOGLE_MAC_RUNTIME_ISOLATION_100X,
  GOOGLE_MAC_RUN_EVIDENCE_LAYOUT_100X, GOOGLE_MAC_TODAY_REUSABLE, GOOGLE_MORNING_MAC,
  GOOGLE_MORNING_WINDOWS, GOOGLE_NONCANDIDATE_GAP_CLOSER_100X, GOOGLE_PILOT_READINESS_100X,
  GOOGLE_POST_INDEX_CROSS_HOST_QA_100X, GOOGLE_PREPARE_MUSE_WALL, GOOGLE_PROOF_PACKET_ASSEMBLER_100X
  (all *_PROMPT.txt / *WORKER_PROMPT.txt in ops/ai/). Every worker following these
  hits a missing file on step one.
- 16× .md (list): ops/ai/live/{GOOGLE_WALL_SLOT01 (notes absence — CORRECT),
  OVERNIGHT_02, OVERNIGHT_03, RESUME_ENDGAME_34B0A42 (intentional history),
  WALL_02 (historical pin)}, MISSIONS/{M1,M2}, MUSE_PACKETS/{M1,M2,M3},
  USER_ACCEPTANCE/{UA-A01,UA-B01}, USER_ACCEPTANCE_{A_STATUS_PHASE,D,E,Z_HANDOFF}.
- Remaining AUTHORITATIVE vocab files (file-level, not line-pulled):
  COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28, COURIER_PERMANENT_MASTER_WORKER_PROMPT.txt,
  GOOGLE_MAC_100X_UNIVERSAL_WORKER_PROMPT.txt, GOOGLE_MAC_RUN_PREP_100X_PROMPT.txt,
  GOOGLE_MORNING_WINDOWS_WORKER_PROMPT.txt, GOOGLE_WINDOWS_LEDGER_G181_G280_WORKER_PROMPT.txt,
  post_ledger_models/CODEX_HIGH_ONCE_FIXED_CANDIDATE_PROMPT.txt.
REPLACEMENT: prompt-maintainer rewrites gate preamble → WALL_QUEUE + HEAD ref +
durable verdict record (once it exists). OWNER: prompt owner / gate owner.

## EXPLICITLY NOT STALE (do not touch)
- ops/ai/PRE_CODEX_HANDOFF.md, GOOGLE_PRE_CODEX_GATE_2026-09-27.md: frozen
  historical artifacts/definitions, not current claims.
- WALL_03/WALL_05/GOOGLE_WALL_SLOT01 e5751783 mentions: legitimate OLD_SHA pins
  with 34b0a42 re-verification.
- MUSE9_M9 buckets: SHA-agnostic.
- `pre_codex_candidate_*`: 0 hits — fully gone with queue rewrite.

## Collateral (non-W4, one line each, for owners)
- UA namespace collision: my A–J files coexist with peer A/C/H/I variants + K–P +
  USER_ACCEPTANCE/ dir + Z_HANDOFF → needs dedupe authority (M9).
- M9 BEFORE_RUN1-7 freeze rule is currently violated (W4-0 is the evidence).

STATUS=W4_LANE_COMPLETE (report-only; 0 edits)

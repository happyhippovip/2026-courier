# Mac Google Overnight Supplemental Queue 120 — 2026-09-27

Status: ACTIVE SUPPLEMENTAL READ_ONLY QUEUE
Purpose: provide additional dependency-safe overnight work after existing queues drain, without inventing architecture or repeating completed work.

## Hard rules

- RESULT_REUSE_FIRST=YES
- MINIMUM_NECESSARY_READS=YES
- NO_BROAD_REPO_SCAN=YES
- NO_BUSYWORK=YES
- NO_DUPLICATE_REVIEW=YES
- APPLICATION_SOURCE_WRITE=NO
- FINAL_CANDIDATE_WRITE=NO
- NO_CODEX
- NO_PHYSICAL_RUN_1_BEFORE_READY_FOR_PHYSICAL_RUN
- NO_RUN_2_BEFORE_RUN_1_PASS
- MAX_HEAVY_JOBS=1
- Do not create WBUILD-031.
- Existing valid durable evidence closes a task without redoing it.
- Candidate/runtime-sensitive evidence must be revalidated only when its binding changed.
- One live claim per task.
- Queue empty after one bounded refresh means TRUE_IDLE.

## Execution

Each worker claims exactly one free G### task, completes or classifies it, persists a compact result, releases its claim, then takes the next READY task.

Result fields:
TASK_ID=
STATUS=PROVEN|OPEN|BLOCKED|OBSOLETE|CONTRADICTED|NEEDS_VERIFICATION
INPUTS_READ=
RESULTS_REUSED=
NEW_EVIDENCE=
MISSING_EVIDENCE=
BLOCKER=
CRITICAL_PATH_IMPACT=
NEXT_DEPENDENCY=
DO_NOT_REPEAT_FINGERPRINT=


## G061-G070 — FINAL CANDIDATE EVIDENCE

G061 — Final SHA presence and base binding from durable handoff only
G062 — Exact five-file changed-scope evidence check
G063 — 12-case matrix completeness audit
G064 — Required targeted-test command inventory
G065 — Required targeted-test result inventory
G066 — Skipped-test count evidence audit
G067 — git diff --check evidence audit
G068 — stale older-SHA evidence rejection audit
G069 — known P0 blocker aggregation
G070 — compact PRE_CODEX handoff readiness summary

## G071-G080 — TRUSTED CONTENT / ARTIFACTS

G071 — Goal->Task expected-hash ownership trace
G072 — Task->dispatch expected-hash propagation trace
G073 — Dispatch->verification expected-hash propagation trace
G074 — worker expected_sha256 rejection evidence
G075 — worker omission bypass prevention evidence
G076 — correct server bytes PASS evidence
G077 — wrong server bytes FAIL evidence
G078 — malformed target fail-closed evidence
G079 — ambiguous target fail-closed evidence
G080 — legacy no-task-expectation behavior evidence

## G081-G090 — REPLAY / IDEMPOTENCY

G081 — identical replay ACK evidence
G082 — identical replay after reload evidence
G083 — changed status rejection evidence
G084 — changed worker rejection evidence
G085 — changed attempt rejection evidence
G086 — changed dispatch generation rejection evidence
G087 — changed artifact result rejection evidence
G088 — canonical-result equivalence field inventory
G089 — duplicate persistence boundary review
G090 — replay acceptance matrix compression

## G091-G100 — RUN_1 PREPARATION

G091 — RUN_1 exact runtime/SHA binding checklist
G092 — RUN_1 isolated workspace checklist
G093 — RUN_1 isolated ports/process ownership checklist
G094 — RUN_1 A-exactly-once proof fields
G095 — RUN_1 real Result A evidence fields
G096 — RUN_1 server-bytes proof fields
G097 — RUN_1 verify/reconcile transition evidence
G098 — RUN_1 B-after-A legality evidence
G099 — RUN_1 HUMAN_RELAY_COUNT=0 evidence
G100 — RUN_1 fail-fast/no-failed-execution checklist

## G101-G110 — RUN_2 PREPARATION

G101 — RUN_2 dependency on RUN_1 PASS
G102 — RUN_2 fresh isolation checklist
G103 — RUN_2 pre-restart persisted-result evidence
G104 — RUN_2 restart cutpoint definition
G105 — RUN_2 no-A-reexecution proof fields
G106 — RUN_2 same-result-preserved proof fields
G107 — RUN_2 post-restart reconciliation proof fields
G108 — RUN_2 B-auto-start proof fields
G109 — RUN_2 A-execution-count=1 proof fields
G110 — RUN_2 final evidence packet template

## G111-G120 — RESTART MATRIX

G111 — Courier process restart scenario coverage
G112 — worker disappears scenario coverage
G113 — result persisted/reconcile missing coverage
G114 — READY-before-dispatch coverage
G115 — dispatch-without-result coverage
G116 — provider temporarily unavailable coverage
G117 — stale result coverage
G118 — identical duplicate coverage
G119 — contradictory duplicate coverage
G120 — restart matrix RSR numerator/denominator readiness

## G121-G130 — PROOF CARDS

G121 — Goal-ID evidence mapping
G122 — Goal-Contract fingerprint mapping
G123 — Task-ID/result mapping
G124 — acceptance-criteria mapping
G125 — Evidence-ID mapping
G126 — Proof-Level mapping
G127 — Source/Build/Runtime fingerprint mapping
G128 — Covered Surface mapping
G129 — UNKNOWN and human-intervention mapping
G130 — revalidation-status mapping

## G131-G140 — CORE FREEZE

G131 — Trusted Ledger PASS prerequisite audit
G132 — LEDGER_FROZEN prerequisite audit
G133 — Reliable Motor PASS prerequisite audit
G134 — Result->Verify->Reconcile->NEXT_READY proof audit
G135 — Zero-Human A->B prerequisite audit
G136 — Restart matrix prerequisite audit
G137 — A4 Covered Surface prerequisite audit
G138 — bounded resources/no-tight-polling audit
G139 — Proof Card completeness audit
G140 — earliest causal Core-Freeze blocker summary

## G141-G150 — WALL RELIABILITY

G141 — atomic claim evidence
G142 — lease expiry/stale claim evidence
G143 — claim ownership identity evidence
G144 — result identity validation evidence
G145 — result deduplication evidence
G146 — RESULT_REUSE_FIRST evidence
G147 — queue dependency unlock evidence
G148 — NEXT_READY deterministic selection evidence
G149 — single-PREPARER refresh-lock evidence
G150 — TRUE_IDLE correctness evidence

## G151-G160 — CONTINUITY / PORTABILITY / COST

G151 — session /clear continuity evidence
G152 — provider-session continuity evidence
G153 — manual account-change continuity evidence
G154 — Mac/Windows path portability evidence
G155 — host-local scratch separation evidence
G156 — MAX_HEAVY_JOBS admission evidence
G157 — resource pressure fallback evidence
G158 — no broad scan/repeated read evidence
G159 — cost/quota stop semantics evidence
G160 — noninterference with Central Writer/peers evidence

## G161-G170 — PILOT PREPARATION

G161 — pilot candidate qualification template
G162 — pilot disqualification criteria
G163 — Goal Contract pilot template
G164 — baseline questionnaire
G165 — pilot duration/exit criteria template
G166 — permission/data-scope template
G167 — retention/deletion template
G168 — setup/support/provider-cost capture template
G169 — HIPG/RSR/NDR capture template
G170 — first-cohort decision template

## G171-G180 — USER REPO / ONBOARDING PREP

G171 — user repo connection requirements review
G172 — least-privilege permission model requirements
G173 — read-only vs write authorization distinction
G174 — idea inbox NOW/NEXT/LATER/PARKED classification
G175 — goal confirmation vs idea capture distinction
G176 — manual pilot onboarding flow
G177 — setup-friction measurement plan
G178 — repo ownership/revocation requirement
G179 — provider-independent durable-state requirement
G180 — future onboarding blockers and pilot-learning questions

## Queue end rule

After G180:
1. harvest unprocessed results;
2. refresh once from canonical truth + explicit Central Writer handoff + open causal blockers;
3. if no concrete authorized READY work appears, TRUE_IDLE;
4. do not create G181 merely to consume capacity.

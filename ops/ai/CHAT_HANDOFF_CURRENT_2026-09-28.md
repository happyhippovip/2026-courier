# Courier Chat Handoff — 2026-09-28 ~17:35 Europe/Berlin

Purpose: paste this into the next ChatGPT chat so it can continue without reopening completed work.

## 1. User goal and working style

The user wants Courier finished as quickly as truthfully possible, with many Muse/Google windows kept useful in parallel.
They strongly prefer exact prompts, exact window numbers, repeat counts, /clear timing, and direct next actions.
Do not waste time with generic reassurance, repeated questions, idle-window filler, broad re-reviews, or old completed Ledger work.
They want both:
1. technical finish path to a real product;
2. a parallel revenue path so Courier can start generating paid pilot revenue.

Language: German. Typo-tolerant. Operational, direct, concise.

## 2. Repo / branches

Repository:
happyhippovip/2026-courier

Coordination branch:
coordination/autofill-task-seed-20260926

Current coordination HEAD at handoff:
b7a26a401136d785f7360d6bdf4490b6fc1d6ae3
message: ops: add scalable 1-24 Windows finish wall with six-pass dosing

Accepted original repair base:
4c1e24ccc522042af826bc4c2b595daf85d097f9

Rejected b2:
83940de3d7d33776a712e7506aa76726d16f8587
Reason historically: weak duplicate equivalence.

Current remote candidate-b-1:
34b0a4264bf763bc2a78f761ffba36e47706b2cf
message: fix(core): apply Q027 Central Writer fix packet with updated test

Direct GitHub verification in this chat confirmed:
refs/heads/candidate-b-1 -> 34b0a426...

## 3. Ledger

Ledger is complete and must stay out of the active queue.

Canonical:
ops/ai/LEDGER_FREEZE_CURRENT.md

Current:
LEDGER_PERCENT=100
LEDGER_STATUS=FROZEN_COMPLETE
LEDGER_ROUTING=DISABLED
LEDGER_REOPEN=RETEST_TRIGGER_ONLY

Do not route normal Muse/Google/Claude/Codex work back to Ledger.
Reopen only the smallest affected family if a concrete durable RETEST_TRIGGER exists.

Known post-Ledger source-truth corrections:
- POST /tasks/result success state = RESULT_RECEIVED
- verifier PASS -> RECONCILED
- VALIDATED_PENDING_VERIFY is not an implemented Courier task state
- ordinary wall_claim files do not generally prove lease/pid/liveness
- old historical READY prose does not override current gate/source/runtime truth

## 4. Executive status

Canonical:
ops/ai/CHIEF_STATUS_CURRENT.md

Operational estimate:
LEDGER=100%
COURIER_PREPARATION≈80%
COURIER_END_TO_END_SHIP_READINESS≈48%

These are operational estimates, not test coverage.

Strong/completed:
- Ledger freeze
- broad post-Ledger QA/evidence design
- remote candidate durability
- trusted-hash / duplicate-result work substantially implemented
- Mac binding/preflight/process/isolation/evidence layouts substantially prepared

Decisive open work:
- exact final Claude/Codex fixed-candidate verdict
- admitted BEFORE_RUN1 fixes
- real producer boundary
- exact Mac binding after review/final code fingerprint
- actual physical RUN_1
- actual physical RUN_2
- Core Freeze
- minimum real pilot
- Product Shell only after positive pilot signal

## 5. Current canonical gate

Canonical:
ops/ai/GATE_STATE_CURRENT.md

Current durable repo state:
PRE_CODEX_STATE=VALIDATING
REPORTED_PRE_CODEX_READY=YES
REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
REMOTE_GITHUB_RESOLUTION=FOUND_ON_candidate-b-1_AS_34b0a426...
AUTHORITATIVE_READY=NO
NEXT=CLAUDE_CODEX_FIXED_CANDIDATE_CONSUME

Important history:
Local Muse evidence previously reported PRE_CODEX_STATE=DURABLE / AUTHORITATIVE_READY=YES / 44/44 exact-SHA adjudication and NEXT=CODEX_HIGH_ONCE.
However the coordination branch is now intentionally conservative at VALIDATING/AUTHORITATIVE_READY=NO until the exact final checklist / Claude-Codex verdict and material invalidation are consumed.
Do not reopen remote durability: remote candidate is confirmed.

No canonical:
ops/ai/live/CODEX_HIGH_RESULT_CURRENT.md
was present at the last repo check.

Therefore do NOT claim Claude/Codex GREEN yet.

## 6. Canonical endgame sequence

ops/ai/CANONICAL_ENDGAME_SEQUENCE_2026-09-28.md

Order:
0 LEDGER FROZEN
1 PRE_CODEX / authoritative candidate state
2 candidate-independent parallel wall
3 optional convergence (Opus optional)
4 exactly one fixed-candidate Claude/Codex HIGH review
5 exact Mac binding
6 RUN_1
7 RUN_2
8 Core Freeze
9 minimum real pilot
10 Product Shell only after positive real pilot signal

Fast-path laws:
- parallelize independent work only
- never parallelize a single-owner gate
- one mutable writer
- one physical Mac owner
- MAX_HEAVY_JOBS=1 per host
- failed physical execution cannot be retried into fake PASS
- actual instance evidence beats templates
- free quota is not a reason to reopen complete families

## 7. Claude / Codex / Opus / Supercode

User decided Claude takes over the Codex/C4 role.

Desired:
Claude Code HIGH, narrow fixed-candidate semantic/code review.
No broad repeated review.
Exactly one review per unchanged material candidate fingerprint.

Earlier Claude attempt returned BLOCKED_ON_READ due tool/classifier outage and could not reread the old base.
After that, GitHub was used directly to verify source.

Opus 4.6 was previously used on a few concrete defects but became unavailable mid-run.
Do not wait for Opus.
Opus is optional, never a gate.

Supercode remains reserve only:
- concrete hard blocker after Claude/Codex; or
- ambiguous RUN_1/RUN_2 failure ordinary C1/C2 cannot safely resolve.
Do not spend it on broad scans.

## 8. Important source truth: result replay

At old base 4c1e24:
server/app.py duplicate result ACK compared only:
(dispatch_id, result_id, status)

At current candidate-b-1 34b0a426:
server/app.py duplicate ACK comparison includes:
(dispatch_id, result_id, status, worker_id, attempt_id, artifacts)

Therefore do NOT reopen the old “worker-blind Case-10” question as if it were unexamined unless source materially changes.

Canonical required semantic direction:
- identical replay -> ACK_DUPLICATE
- changed status -> reject
- changed worker -> reject
- changed attempt -> reject
- changed dispatch -> reject
- changed artifact result -> reject

Trusted expected_sha256 authority stays task-owned; worker result must never control the verifier’s expected hash.

## 9. Required 12 verifier/replay cases

Keep these stable:
1 task-owned expected survives
2 correct bytes PASS
3 wrong bytes FAIL
4 worker expected rejected
5 worker omission cannot bypass expectation
6 no task expectation legacy-only
7 malformed/ambiguous target FAIL
8 identical replay ACK
9 changed status rejected
10 changed worker rejected
11 changed attempt/dispatch rejected
12 changed artifact result rejected

SKIPPED invalidates a handoff.

## 10. Opus/local fixes reported during this chat

A local Opus run reported:
- negative idempotency FAIL-retry semantics fixed/tested
- WB01 synthetic-reject gate false-green fixed/tested
- RUN_2 verifier contract fixed: A must not be reverified, B verification remains legal
- proof hash-chain producer/verifier compatibility fixed/tested
- 98/98 unit tests green in that local context
- 12/12 verifier selftests green

Important:
Do NOT assume those local changes are all in remote candidate-b-1.
Some were in local/unpublished writer stacks / working trees.
Always distinguish durable candidate source from local working-tree evidence.

## 11. Real producer / RUN_1 blocker

This is a major current BEFORE_RUN1 concern.

Muse on Mac read the active working tree and found:
scripts/run_physical.py contains a synthetic/STUB producer path and writes evidence marked synthetic.
scripts/run1_physical/verify_proof_contracts.py correctly fails closed on synthetic evidence.
The verifier selftest reported 12/12 PASS.

Muse concluded:
- a physical RUN_1 using that stub would be rejected
- simply deleting the synthetic flag is NOT enough
- underlying simulated transitions / fabricated payload behavior must be replaced by a real producer/effect boundary
- do not run RUN_1 until this is truly closed and READY_FOR_PHYSICAL_RUN is explicit

Owner:
single Windows Central Writer for implementation;
Mac physical owner only after gate/fix.

## 12. RUN_1 acceptance

Exactly one physical Mac runner.

Must prove:
A exactly once
-> real Result A
-> task-owned expected hash
-> exact server bytes
-> independent Verify
-> Reconcile
-> B becomes NEXT_READY / dispatches / starts / completes automatically
-> HUMAN_RELAY_COUNT=0
-> no FAILED execution

Any FAILED execution invalidates RUN_1.
Never retry a failed physical run into a fake PASS.

## 13. RUN_2 acceptance

Only after RUN_1 PASS.

Must prove:
- A result persists
- controlled restart
- A is not re-executed
- A is not reverified as a fresh execution
- legitimate B verification remains allowed
- stale dispatch/result/worker paths are rejected
- B continues automatically
- A execution count remains 1

## 14. Core Freeze

Required:
- Ledger frozen
- Reliable Motor
- Result -> Verify -> Reconcile -> NEXT_READY
- zero-human A -> B
- restart/no-replay
- Covered Surface
- bounded resources / no tight polling
- exact Proof Cards/fingerprints
- zero gate-violating UNKNOWNs

## 15. Physical Mac safety / known preflight

Mac evidence observed:
- exact final SHA binding/preflight has been heavily prepared
- production-ish processes on 8080 / existing daemon/verifier were treated as foreign
- staging port 8081 was identified as the safe alternative in that session
- do not kill foreign processes
- own PID/PGID only
- one physical owner
- one heavy job per host
- resource gate can block boot
- physical RUN evidence has not yet been canonically accepted

Do not invent a physical PASS from prep documents.

## 16. Model/window setup

Muse:
Muse Code 1.4.0
model shown: muse-spark-1.3-contributor
often xhigh / YOLO

Google:
Antigravity / Gemini on Windows and Mac

Claude:
HIGH for fixed-candidate C4/Codex role

Premium budget:
- Opus optional and scarce/unavailable
- Supercode reserve
- do not waste premium on broad QA

## 17. Window ownership rules

Muse:
READ_ONLY adversarial QA.
No application-source edits.
No physical RUN_1/RUN_2.

Google Windows:
one source writer only.
Read-only packet workers can run in parallel.
Only explicit writer slot/claim may edit application source.

Google Mac:
prep/evidence/review in parallel.
Physical execution exactly one owner.

## 18. Local Swarm taskbank

Files:
ops/ai/AUTO_SWARM_TASKBANK_2026-09-28.json
scripts/local_swarm_claim.py
ops/ai/TURBO_REPEATABLE_CLAIM_LOOP_PROMPT.txt

Original bank sizes:
windows-google = 192
mac-google = 64
muse = 288
muse-windows = 144
muse-mac = 144
total = 832

These are ORIGINAL counts, not guaranteed remaining counts.
Local completion state lives under .courier_swarm and is host-local.

To inspect real remaining local work:
python scripts/local_swarm_claim.py status

Repeatable claim behavior:
- claim fresh task
- persist ops/ai/live/<TASK_ID>.md
- complete/block claim
- claim next
- 3-6 tasks per invocation
- NO_TASK / POOL_EXHAUSTED -> stop; do not invent filler

## 19. 2x / 3x / 6x dosing

Canonical:
ops/ai/WINDOW_DOSE_PLAYBOOK_2X_3X_6X_2026-09-28.md

Meaning:
2x = probe dose
3x = normal work dose
6x = drain dose only if real work remains

Recommended:
Muse Mac: 3x -> /clear -> 3x if NEXT_AVAILABLE
Generic Muse: 2x -> /clear -> 2x -> /clear -> 2x
Muse Windows: 2x -> /clear -> 2x; optional +2x if NEXT_AVAILABLE
Google Windows read-only: 2x -> /clear -> 2x; optional +1-2x
Windows sole writer: 1x at a time
Google Mac prep: 2x -> /clear -> 1-2x
Physical Mac owner: one controlled run prompt at a time

Never queue another dose after:
POOL_EXHAUSTED
NO_TASK
FAMILY_COMPLETE
BLOCKED_OTHER_OWNER without newly satisfied dependency

## 20. /clear rules

Never /clear:
- mid-claim
- mid-source patch
- mid-test that owns mutable state
- mid-physical RUN_1/RUN_2
- before checkpoint/result is persisted

Before /clear:
1 finish current claim/pass
2 persist checkpoint
3 complete/block/release claim
4 persist owner/gate dependency
5 ensure no uncommitted source change would be lost

Good rhythm:
read-only Muse/Google: after 2-3 doses
Central Writer: only after patch/test/checkpoint/commit boundary
Physical owner: only after complete run verdict/evidence boundary

## 21. Wave files created

Important wall generations:
- ops/ai/MUSE_CLAUDE_CODEX_SIDECAR_16_2026-09-28.md
- ops/ai/ENDGAME_WAVE3_ASSIGNMENT_2026-09-28.md
- ops/ai/ENDGAME_WAVE4_ASSIGNMENT_2026-09-28.md
- ops/ai/ENDGAME_WAVE5_MARATHON_ASSIGNMENT_2026-09-28.md
- ops/ai/ENDGAME_WAVE6_DEEP_RESERVE_2026-09-28.md
- ops/ai/FINISH24_WINDOWS_SLOT_MAP_2026-09-28.md
- ops/ai/FINISH24_DOSE_MATRIX_2026-09-28.md

Wave 5 = marathon lanes.
Wave 6 = deeper 12-14-step reserve lanes.
FINISH24 = scalable 1/6/12/15/18/21/24 Windows wall.

## 22. FINISH24 current wall

Files:
ops/ai/FINISH24_WINDOWS_SLOT_MAP_2026-09-28.md
ops/ai/FINISH24_MUSE_WINDOWS_PROMPT.txt
ops/ai/FINISH24_GOOGLE_WINDOWS_PROMPT.txt
ops/ai/FINISH24_DOSE_MATRIX_2026-09-28.md

Slots 01-24:
01 CHIEF_CRITICAL_PATH
02 REAL_PRODUCER
03 RESULT_REPLAY_IDENTITY
04 TRUSTED_HASH_ARTIFACT
05 STATE_DURABILITY_ATOMICITY
06 WORKER_LIVENESS_RECLAIM
07 RETRY_REQUEUE_GENERATIONS
08 VERIFY_RECONCILE
09 NEXT_READY_B_AUTOSTART
10 EVENT_TIMESTAMP_ORDER
11 PROCESS_TIMEOUT_REAP
12 TARGETED_TEST_INVALIDATION
13 CLAUDE_CODEX_INTAKE
14 MAC_EXACT_BINDING_HANDOFF
15 RUN1_ACTUAL_WITNESS
16 RUN1_FAILURE_STICKINESS
17 RUN2_RESTART_NO_REPLAY
18 CROSS_RUN_ISOLATION
19 CORE_FREEZE
20 PILOT_TECHNICAL_ACCEPTANCE
21 PAID_PILOT_READINESS
22 ROLLBACK_LKG_RELEASE
23 ONBOARDING_SUPPORT_OBSERVABILITY
24 FINAL_SYNTHESIS_TO_PRODUCT

Each slot has six sequential passes:
P1 SOURCE_TRUTH
P2 ADVERSARIAL_MATRIX
P3 TEST_GAP
P4 EVIDENCE_MINIMALITY
P5 PHASE_TRANSITION
P6 CLOSEOUT

Repeated invocation MUST execute next unfinished pass only.
After P6:
FAMILY_COMPLETE=YES
DO_NOT_REPEAT.

Dose matrix:
1 window: slot01 6x, clear after 2 and 4
6 windows: slots01-06 3x -> clear -> 3x
12/15/18: 2x -> clear -> 2x -> clear -> 2x
21/24: same, final 2x only unfinished slots

Only Google Windows Slot 01 may be the mutable source writer.
Muse FINISH24 is read-only.

## 23. Key commits created in this chat

Important known commits:
d3865693... Ledger freeze / no-Opus / canonical endgame files
0471ca65... Mac pre-Codex bridge
a377236c... Muse return harvest + Windows gate prompt
c8912312... window capacity feature 8/12/16/32
9927aaaad0ad0ea0898d637c626a96750159991e model usage telemetry/subagent orchestration
15357939d55ea2f4ae5fe1252505475df9457726 turbo endgame prompts
fd20d233d640c815dc5ec353191e60b8af0d964e Muse Claude/Codex sidecar 16
514fb912e90bbd47174895ad55c282ecad39bae5 Wave 3
1ef85bbfa742b98f73a6612b4092d77540513d21 Wave 4
4c358fad24feb38086beb3395d4ad549ba9012a9 Wave 5 marathon
d02e7c7881920ba78e0ca2771d062a9b95b539ec Chief status
5d34b2fbbbd95b6fe1336248c3517046bcd2ee44 repeatable claim loop
7d3430306f17076727641e09753d29e024c56dd4 2x/3x/6x dose playbook
0f2b82d697051a6a4a71464df7ec6a9205980087 retired stale remote-durability blocker / updated gate
2cf4de56ffd55793179b2c3ff1904e63c26c8555 Wave 6 deep reserve
a4c224eb21b95ad68f3800e33f342c4d17bc0bee revenue founding-pilot track
b7a26a401136d785f7360d6bdf4490b6fc1d6ae3 scalable FINISH24 wall

Older useful:
b77801f844787f0d2cdb0339d2bdd9ff057b97a0 roadmap
44797a26dbafaa40966b082260d4f03e83e72c1d Muse Cascade
a0ae1959... future Muse 97-144 phase-gated queue
eb701c...,319c54e...,e09089...,7fa0e2...,be87fe... earlier direct-50 queue work

## 24. Window-capacity feature

Commit:
c8912312fb70051eb51827c9ed48a58dc6935d9e

Files:
scripts/window_capacity_policy.py
config/window_capacity_policy.json
dashboard server/index/app/style
tests/test_window_capacity_policy.py
docs/WINDOW_CAPACITY_PROFILES.md

Supports target slots:
8 / 12 / 16 / 32
pause/resume
hide/show
persistent runtime state
drain on scale-down

Safety invariants stay:
writers=1
heavy jobs=1

## 25. Usage telemetry / subagents

Commit:
9927aaaad0ad0ea0898d637c626a96750159991e

Files:
ops/ai/MUSE_SUBAGENT_ORCHESTRATOR_PROMPT.txt
ops/ai/MODEL_USAGE_TELEMETRY_POLICY_2026-09-28.md
scripts/record_model_usage.py
ops/ai/ENDGAME_WINDOW_ASSIGNMENT_2026-09-28.md

Safe telemetry only:
provider/model class
task ID
input/cached/output tokens
turns
subagents_used
status
findings
duplicate skips

Never commit:
account/email/payment/subscription/quota reset/API keys/private chats.

Muse native subagents:
up to 3 read-only subagents in up to 4 parent windows
roles:
SOURCE_TRUTH
ADVERSARIAL_FALSIFIER
EVIDENCE_MINIMALITY
No nested subagents.
Do not use subagents when existing evidence already answers the question.

## 26. Revenue track

Canonical:
ops/ai/COURIER_REVENUE_TRACK_CURRENT.md

Offer:
Courier Founding Pilot
EUR 390 one-time
7 days
first three paid pilot targets
one real AI-heavy workflow

Sold honestly as:
- onboarding/workflow mapping
- continuity/handoff setup
- one defined real workflow
- evidence-based pilot
- operator support
- end-of-pilot report

Do NOT claim:
- production-ready SaaS
- zero bugs
- fully autonomous operation before gates prove it
- guaranteed savings/revenue

Commercial target:
3 x EUR 390 = EUR 1,170 if three customers buy.
Target, not guarantee.

Potential later recurring plan to validate:
EUR 79-149/month or higher managed service
but do not pre-commit before pilot evidence.

Revenue files:
ops/ai/COURIER_REVENUE_TRACK_CURRENT.md
ops/ai/COURIER_REVENUE_MUSE_PROMPT.txt
ops/ai/COURIER_REVENUE_GOOGLE_PROMPT.txt
ops/ai/COURIER_REVENUE_6_DOSE_SALES_PROMPT.txt

Suggested revenue windows:
4-6 commercial windows only.
Goal = sent messages / booked calls / paid pilots, not infinite marketing docs.

Revenue counters:
PEOPLE_CONTACTED
CALLS_BOOKED
PAID_PILOTS
EUR_COLLECTED

Do not chase speculative trading returns as the revenue plan.
Use product/service sales as the controllable path.

## 27. Immediate next actions for the next chat

First thing:
1. Read current repo:
   ops/ai/GATE_STATE_CURRENT.md
   ops/ai/CHIEF_STATUS_CURRENT.md
   ops/ai/live/CODEX_HIGH_RESULT_CURRENT.md if it exists
   current FINISH24 checkpoints
2. Check whether Claude/Codex verdict has appeared.
3. Check whether real producer blocker has been fixed durably.
4. Check whether an explicit READY_FOR_PHYSICAL_RUN exists.
5. Check whether actual RUN_1 evidence exists.
6. Route immediately to earliest unfinished critical-path item.

If no Claude/Codex verdict:
- do NOT reopen remote durability
- do NOT reopen Ledger
- continue useful FINISH24/claim work in parallel
- get one Claude HIGH fixed-candidate verdict

If Claude/Codex BLOCKED:
- confirm exact defect only
- one Windows Central Writer fixes smallest causal scope
- targeted invalidated tests
- new fingerprint/SHA if material source changed
- re-review only if material candidate changed

If Claude/Codex GREEN:
- sole Windows writer closes admitted BEFORE_RUN1 fixes, especially real producer if still open
- targeted tests
- exact Mac handoff
- then one physical Mac owner

If RUN_1 PASS:
- immediately RUN_2
If RUN_2 PASS:
- Core Freeze
If Core Freeze PASS:
- minimum real paid/real pilot
If pilot positive:
- Product Shell

## 28. Things the next chat must NOT do

- do not reopen Ledger
- do not send Muse back to old 65-96/Cascade families
- do not treat free windows as a reason to re-review unchanged source
- do not claim canonical Claude/Codex GREEN without a durable result
- do not confuse local working-tree fixes with candidate-b-1
- do not start physical RUN_1 with synthetic/stub producer
- do not let multiple Windows writers edit source
- do not let multiple Mac windows execute physical runs
- do not retry physical FAIL into PASS
- do not kill foreign processes
- do not start Product Shell before positive real pilot evidence
- do not waste Opus/Supercode on broad scans
- do not make revenue claims Courier has not proven

## 29. Preferred assistant behavior

Answer in German.
Be typo-tolerant.
Give exact prompts and counts when requested.
Use repo truth before stale transcript truth.
For GitHub facts use GitHub connector.
When user asks for more wall work, first check phase and avoid duplicate work.
Prefer 2x/3x/6x dosing and FINISH24 pass progression.
Tell user explicitly when /clear is safe/needed.
Keep the critical serial owner moving even while many windows run in parallel.

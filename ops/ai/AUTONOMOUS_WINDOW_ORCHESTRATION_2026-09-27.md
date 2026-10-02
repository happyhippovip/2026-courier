# Courier Autonomous Window Orchestration — Day 2 — 2026-09-27

Status: ACTIVE coordination policy.

Goal: finish Courier with minimum human relay. Window count is a resource, not a goal.

## 1. Human interaction target

The owner should not manually coordinate dozens of workers.

Until Courier itself can own this queue, ChatGPT acts as coordinator:
- choose the next gate
- assign non-overlapping roles
- name the exact machine/window
- specify run count
- stop duplicate work
- reserve expensive reviewers for decision-changing gates

User-facing instructions should be short:
`WHERE -> WINDOW -> ACTION -> COUNT`.

## 2. Current ordering

Do not reorder without new evidence:

1. FINAL_CANONICAL_CANDIDATE
2. REAL_TARGETED_TESTS
3. CODEX_FINAL_HIGH_REVIEW
4. EXACT_MAC_RUNTIME_BINDING
5. RUN_1_PHYSICAL_A_VERIFY_B
6. RUN_2_RESTART_NO_A_REPLAY
7. MINIMUM_HONEST_DUAL_SURFACE_UI
8. OWNER_USES_UI
9. FIRST_FRIEND_TRIAL
10. A->B->C->D / branches / bounded loops
11. bounded scale + soak
12. product shell / packaging / update / rollback
13. broader community/world/social features

Muse stdout contract is already CLOSED/MATCH.

## 3. Writer ownership

### Until FINAL_CANONICAL_CANDIDATE closes

WINDOWS ANTIGRAVITY CENTRAL WRITER is the ONLY source writer for the final candidate.

Google and Muse:
READ-ONLY evidence/review/support.

Do not disturb the Windows writer with unrelated work.

### After RUN_2

Google and Muse may become primary bounded writers for later work, but:
- exactly one writer per bounded task/file ownership scope
- non-overlapping write scopes
- each task has acceptance evidence
- no two writers edit the same subsystem concurrently
- one integrator owns merge/reconciliation

A free Google writer may be held READY, but receives no final-candidate source write while Windows owns that gate.

## 4. Reviewer budget

CODEX:
Use for code-grounded gate reviews that can change ship/no-ship:
- once on final candidate + real test evidence
- later on complex verified graph-engine transitions (A->B->C... branches/loops) when implementation is ready for a gate
- security/release review only when concrete implementation exists

Do not use Codex for routine archaeology or repeated summaries.

OPUS ULTRACODE:
Use for high-level convergence/product/security decisions when a real choice remains.
Do not use for routine code writing or repeated vision restatement.

## 5. Pre-clear reset

Before clearing old windows:
- each Muse window: run MUSE pre-clear context harvest once
- each Google window: run GOOGLE pre-clear context harvest once
- preserve only P0/P1 unique transfer blocks
- DROP duplicate/obsolete P2 noise
- then /clear

Fresh windows should NOT all reread the repo immediately.

They stay idle until the coordinator assigns a specific bounded job.

## 6. Fresh-window pool after clear

Recommended starting pool:

WINDOWS:
- W1 = existing final candidate writer. Do not disturb.
- W2 = read-only standby/auditor only until final candidate closes.

GOOGLE:
- G1 = final-candidate scope/base auditor
- G2 = trusted-hash / contract auditor
- G3 = duplicate/replay auditor
- G4 = targeted-test evidence auditor
- G5 = idle reserve / future bounded writer after RUN_2

MUSE:
- M1 = RUN_1 evidence/runbook auditor
- M2 = RUN_2 restart/no-replay auditor
- M3 = contradiction/stale-evidence hunter
- M4 = Mac binding/runtime identity auditor
- remaining Muse windows = IDLE unless a unique P0/P1 task exists

MAC ANTIGRAVITY:
- physical runner only
- one heavy slot
- no source writing during proof unless a newly proven blocker explicitly changes scope

CODEX:
- idle until final SHA + test evidence

OPUS:
- idle until a genuine judge/convergence decision

## 7. Gate transition rules

### FINAL CANDIDATE gate

Required:
- final SHA
- base proven from candidate-b-1
- exactly authorized correction scope
- trusted task-owned expected hash
- duplicate/replay semantics corrected
- real targeted tests
- no skipped evidence handoff

When ready:
STOP broad analysis.
Send exactly one Codex High review.

### CODEX gate

If PASS / READY_FOR_PHYSICAL_RUN:
do not reopen architecture.
Proceed to Mac.

If FAIL:
create one bounded correction task for Windows writer.
No swarm rewrite.

### RUN_1

Exactly one physical run.

PASS requires:
- final runtime SHA bound
- A executed once
- trusted expected content
- server-side exact-content verification
- A reconciled
- B actually starts automatically after verification
- B completes
- human relay A->B = 0
- no FAILED execution

Any failed execution invalidates that run.
Do not retry into a fake PASS.

### RUN_2

Only after RUN_1 PASS.

Exactly one controlled restart proof:
- A executes once
- reaches RESULT_RECEIVED
- verifier initially off
- restart
- same result survives
- A not reexecuted
- verification completes
- B starts automatically and completes

### First UI

Only after RUN_2.

Build the smallest truthful read-only dual surface.
Reuse visual dashboard pieces only; do not reuse fake/demo activity logic.

USER = simple.
OWNER = observability/details.
Same reconciled evidence.

## 8. After RUN_2: make the system work for the owner

Priority is to remove the owner's need to babysit terminals.

Phase A:
- honest status projection
- waiting/blocker reason
- reported vs verified
- next legal action
- retry/replay visibility
- safe stop

Phase B:
- durable work queue
- bounded worker assignment
- automatic continuation
- restart/recovery
- one owner surface

Phase C:
- A->B->C->D
- branches
- bounded loops
- waits/retries/human gates
- multi-host/provider

Only then scale logical windows aggressively.

## 9. Window-count law

Do not use a free window just because it is free.

A window is active only if its task:
- advances the current gate
- reduces a documented P0/P1 risk
- creates reusable acceptance evidence
- prepares the immediately following gate without touching locked source scope

Otherwise it stays idle.

## 10. Communication format

Coordinator replies should default to:

STATUS:
<very short>

NOW:
<symbol> <machine/window> -> <action> -> <count>

NEXT:
<only the next gate>

STOP IF:
<single condition>

Use:
🪟 Windows
🍎 Mac
🟨 Google
🟣 Muse
🧠 Codex
🧿 Opus
✍️ write
👀 read-only
▶️ execute
🧪 test
🔒 wait
✅ proven
⚠️ check
❌ fail

## 11. End goal

The owner should eventually be able to use the computer normally while Courier continues bounded work itself.

Do not claim that this autonomy is already proven.

The next proof of that direction is:
RUN_1 -> RUN_2 -> honest owner UI -> durable autonomous queue.

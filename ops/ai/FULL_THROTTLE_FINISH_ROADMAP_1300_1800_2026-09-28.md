# Full-Throttle Finish Roadmap — 2026-09-28 — 13:00–18:00

Created from durable repo state + current Muse readbacks.

Current durable blocker:
PRE_CODEX_STATE=DURABILITY_PENDING
AUTHORITATIVE_READY=NO
reported FINAL_SHA not durably resolvable.
Single owner: Windows Central Writer.

This is a stretch finish target, not a guarantee. Each downstream phase starts only if its gate passes.

## 13:00–13:30 — Unblock + converge in parallel
Windows:
- exactly ONE Central Writer runs ops/ai/WINDOWS_SINGLE_PRE_CODEX_DURABILITY_OWNER_PROMPT.txt
- goal: make intended final candidate durably resolvable and persist authoritative gate once.

Muse:
- 16–32 windows run ops/ai/MUSE_WHATS_LEFT_AND_WORK_PROMPT.txt
- candidate-independent work only; no blocked 65–96 router.

Opus 4.6:
- 4–6 windows, HIGH/XHIGH
- use OPUS46_PRE_CODEX_CONVERGENCE_MASTER_PROMPT + Finish Six.
- goal: deduplicate defects and give smallest before-Codex / before-RUN1 fix set.

Checkpoint 13:30:
A) AUTHORITATIVE_READY=YES -> start exactly one Codex HIGH.
B) still NO -> Codex stays off; Windows remains sole gate owner; Muse/Opus only legal independent work.

## 13:30–14:15 — Codex window (only if gate ready)
Codex:
- exactly one HIGH fixed-candidate review using CODEX_HIGH_FIXED_CANDIDATE_ONCE_PROMPT.txt.

Muse:
- stop PRE_CODEX-adjacent work.
- review only handoff ambiguity / candidate-independent physical-proof prep.

If Codex BLOCKED:
- Windows Central Writer applies smallest exact defect packet.
- rerun only invalidated targeted evidence.
- new authoritative candidate -> Codex review only if fingerprint materially changed and gate is re-established.

If Codex GREEN:
READY_FOR_PHYSICAL_RUN=YES -> Mac exact binding.

## 14:15–15:00 — Exact Mac binding + RUN_1
One Mac physical owner only.
- bind exact FINAL_SHA/source/build/runtime/config
- fresh isolated run dirs/state/logs/artifacts
- process/resource preflight
- execute RUN_1 once

PASS requires:
A exactly once
real Result A
task-owned expected hash survives
exact server bytes
independent Verify
Reconcile
B automatic start/complete after A
HUMAN_RELAY_COUNT=0
zero FAILED execution

Any FAILED execution invalidates RUN_1.

Muse after evidence appears:
- switch to actual-instance QA, not templates
- audit RUN1 proof instance / A once / hash / verify-reconcile / B autostart / zero relay / failure contamination.

## 15:00–15:45 — RUN_2 restart/no replay
Only after RUN_1 PASS.
One Mac physical owner:
A once -> persist result -> controlled restart -> A not re-executed -> reconcile -> B auto-continues -> A count stays 1.

Muse:
actual RUN_2 instance QA:
restart boundary
no A replay
execution count
B continuation
stale result
stale worker
ordering
cross-run contamination

## 15:45–16:30 — Core Freeze
Converge:
Trusted Ledger
Reliable Motor
Result->Verify->Reconcile->NEXT_READY
zero-human A->B
restart/no-replay
Covered Surface
resource bounds/no tight polling
Proof Cards/fingerprints
zero gate-violating UNKNOWNs

Muse:
Core Freeze falsification only.
Opus:
one convergence/arbiter pass if evidence conflicts remain.

## 16:30–17:30 — Minimum real pilot
Only if Core Freeze is durable.
Run minimum real Goal Contract/pilot.
Capture:
setup time
human interventions
result success/reliability
support burden
provider cost
positive/negative/unknown user-value signal.

No Product Shell unlock without positive real-pilot signal.

## 17:30–18:00 — Finish/freeze or exact remaining blocker
If positive pilot:
- freeze proof bundle
- record LKG/rollback/update readiness
- Product Shell scope only from pilot-proven needs
- produce final owner-free handoff/release candidate.

If pilot is negative/unknown:
- do not fake completion
- produce one exact remaining causal blocker and stop unrelated work.

## Stop-doing rules
- no second PRE_CODEX validator
- no repeated 65–96 blocked router
- no Ledger work
- no repeated deterministic tests absent invalidation
- no token/quota burn as a goal
- no Codex before authoritative ready
- no physical RUN before Codex green
- no Product Shell before positive pilot

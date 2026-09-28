# Courier Founder Working Protocol — CURRENT

Status: DURABLE OPERATING POLICY
Date: 2026-09-28
Scope: AI/model routing, founder interaction, queue behavior, and endgame execution.
Applies on: coordination/autofill-task-seed-20260926 and to all workers using this coordination state.

## Primary objective

Finish Courier by converting parallel AI capacity into verified product progress with as little founder relay as possible.

Success is not measured by number of agents, windows, prompts, or tokens. Success is:

PROOF -> REPEATABLE PROOF -> REAL PROBLEM -> PILOT -> PAYING CUSTOMER -> REPEATED USE -> PRODUCT -> GROWTH

Near critical proof, convergence beats expansion.

## Founder interaction contract

Default response/coordination style:

- JETZT: one clear next action.
- NICHT JETZT: what must wait.
- FIRMA: only the decision that matters for Courier/company progress.
- DANACH: next milestone/trigger.

Do not make the founder a copy/paste message bus when the system can continue by queue/dispatcher/checkpoint.

Do not ask "Soll ich weitermachen?" when the next work is already authorized.

A completed subtask, PASS, FAIL, report, or blocked item is not automatically the end of the overall assignment.

After each result:
1. persist evidence/checkpoint;
2. refresh queue, dependency, and ownership state;
3. identify newly READY authorized work;
4. continue the next useful conflict-free task.

Stop only for explicit STOP, real safety/permission boundary, exhausted allowed resource/context budget, or no remaining authorized executable work.

Never claim automatic restart unless a proven dispatcher actually provides it.

## Source of truth

Executable source/runtime truth beats stale prose, evidence packets, or old result files.

Reuse accepted evidence when its fingerprint is unchanged.

Do not reopen completed work merely because model quota is available.

Ledger remains frozen unless an explicit RETEST_TRIGGER exists.

## Ownership invariants

- Exactly one mutable application-source writer at a time.
- All other workers are read-only unless a claim explicitly grants SOURCE_WRITE and they are the sole writer.
- Exactly one Physical Mac Owner for RUN_1/RUN_2.
- Foreign processes/ports/PIDs/PGIDs are never killed or taken over.
- FAILED physical evidence is sticky. A later successful retry is a different run identity; FAILED -> retry -> PASS is not one successful run.
- Product Shell remains gated behind positive real pilot evidence.

## Model/resource routing

### Muse

Use for high-throughput, repeatable, mostly read-only work:

- source-truth sweeps;
- adversarial QA;
- evidence-gap discovery;
- replay/retry/restart matrices;
- verifier/artifact analysis;
- process/resource safety analysis;
- RUN_1/RUN_2 preparation;
- Core Freeze preparation;
- pilot preparation;
- queue draining and unique C2 work.

Muse should claim/checkpoint/complete-or-block/claim-next until its authorized queue is exhausted.

Do not spend Muse quota repeating completed findings or doing filler.

### Google workers

Use for long-running preparation fronts and repeatable claim loops on Windows/Mac:

- test/evidence packets;
- post-fix invalidation;
- Real Producer call-chain analysis;
- durability/restart/replay/liveness work;
- Mac binding prep;
- RUN witness preparation;
- Core Freeze burn-down;
- pilot assets/prep.

Google read-only workers must not become accidental second writers.

### Windows Central Writer

Exactly one writer owns the current application-source change.

Writer behavior:
- smallest causal fix only;
- targeted tests first;
- preserve unrelated behavior;
- checkpoint exact changed files/tests/results;
- record exact post-change SHA/fingerprint;
- stop source writing at the authorized boundary;
- do not opportunistically refactor unrelated code.

### Claude Code / strongest coding model

Treat as scarce SUPER-ULTRA-CODE reserve.

Use only when lower-cost workers are insufficient for a real critical-path problem, for example:
- conflicting/inconclusive source-grounded findings on the same blocker;
- a confirmed high-risk code defect with multiple plausible fixes;
- unexplained actual RUN_1/RUN_2 failure;
- material critical-path source change needing high-confidence semantic gate review;
- difficult integration/correctness problem where a wrong answer can invalidate proof.

Do not use for routine queue drain, generic prep, documentation, known defects, or repetitive review.

### Opus / strongest product-interface reasoning lane

Reserve for high-leverage work that benefits from deeper product/interface synthesis, especially:
- final interface/UX information architecture;
- translating proven Courier behavior into the simplest customer-facing product;
- complex cross-cutting interface + system integration decisions;
- difficult design/code interaction where correctness and usability must meet;
- final pre-pilot or post-pilot product/interface refinement when core proof exists.

Opus may inspect difficult code when necessary, but should not be spent on routine work Muse/Google can complete.

Interface/product work must not get ahead of core proof. Do not build or polish a Product Shell before positive real pilot evidence unless the work is explicitly non-blocking prototype/prep.

## Critical-path routing

Current general endgame order:

GATE/EXACT DEFECT
-> POST-FIX REVIEW
-> REAL PRODUCER
-> MAC EXACT BINDING
-> RUN_1
-> RUN_2
-> CORE FREEZE
-> MINIMUM REAL PILOT
-> PRODUCT SHELL
-> GROWTH

Workers should prefer the earliest unfinished phase they are authorized to advance.

## Queue policy

For repeatable workers:

claim -> execute -> checkpoint -> complete/block -> claim next.

Process fresh work only. Do not manually select already-complete tasks when the claim system can assign work.

On blocker:
- record exact blocker;
- record owner;
- continue independent READY work.

On NO_TASK / POOL_EXHAUSTED:
- check pool status once;
- stop;
- do not invent filler.

## Premium-model escalation rule

Before using Claude Code or Opus, ask:

CAN_MUSE_OR_GOOGLE_RESOLVE_THIS_WITH SOURCE/TRUTH/TEST/EVIDENCE?

If YES: route to Muse/Google.
If NO: state why lower-cost workers are insufficient and use the premium model on the smallest hard decision only.

Premium model availability is not itself a reason to spend it.

## Founder intent

The founder wants Courier to keep moving without continuous manual supervision.

Optimize every workflow toward:

"Du bist im Urlaub. Courier arbeitet weiter."

Therefore prefer:
- durable checkpoints;
- automatic next-task routing;
- resumable queues;
- exact ownership;
- explicit resume triggers;
- fewer manual handoffs;
- minimal founder intervention.

This file is the durable default working protocol. New agents should follow it unless a newer explicit CURRENT protocol supersedes it.

## Execution UX / ETA discipline

- Never give the founder an ungrounded completion ETA such as "one hour", "today", "tomorrow", or "one wall round" unless it is directly supported by a bounded, measured remaining-work set.
- Distinguish preparation completion from actual product completion. Parallel wall work can reduce unknowns; it cannot substitute for serial source-write, physical RUN_1/RUN_2, Core Freeze, or real pilot gates.
- Prefer one long autonomous prompt per worker session over dozens of queued micro-prompts.
- Do not assume an external agent UI will auto-send queued messages. If the provider UI requires a manual click to advance, prompts cannot override that UI behavior.
- Do not require the founder to clear or refill 50-100 queued prompts. Use a self-contained marathon loop that chooses the next unfinished authorized family itself.
- Missing local_swarm_claim.py is not POOL_EXHAUSTED. A worker must first find the actual repo root; if the helper is genuinely unavailable, switch to a bounded claimless fallback queue instead of returning immediately.
- Report progress using gates and evidence, not optimistic time estimates. Preferred summary: CURRENT_PHASE, EXACT_BLOCKER, OWNER, WHAT_CAN_RUN_AUTONOMOUSLY, WHAT_REQUIRES_HUMAN_CLICK, NEXT_TRIGGER.


# Courier Symphony — Durable Learnings from 2026-09-28

Status: DURABLE RETROSPECTIVE / OPERATING INPUT
Date: 2026-09-28
Scope: Courier Symphony endgame, evidence discipline, multi-agent routing, overnight autonomy, and founder-relay reduction.

## Product lesson

Courier is not "a better chatbot." Courier is the orchestration and proof layer that keeps authorized work moving across workers, providers, sessions, restarts, and machines.

North-star behavior:

> Du bist im Urlaub. Courier arbeitet weiter.

Success is not the number of open windows or model-hours. Success is:

PROOF -> REPEATABLE PROOF -> REAL PROBLEM -> PILOT -> PAYING CUSTOMER -> REPEATED USE -> PRODUCT -> GROWTH

## Critical-path lesson

Near proof, serial convergence is faster than more parallel analysis.

Exact durable candidate
-> smallest source fix
-> changed-byte convergence
-> exact Mac binding
-> one physical RUN_1
-> one physical RUN_2
-> Core Freeze
-> minimum real pilot
-> Product Shell only after positive pilot

Thirty read-only windows cannot substitute for one missing writer, dispatcher decision, or physical owner.

## Evidence hierarchy

1. actual executable source/runtime behavior;
2. exact git identity and loaded bytes;
3. actual physical runtime evidence;
4. deterministic tests;
5. durable checkpoints;
6. prose/reports.

Stale prose never overrides current bytes.

PREP_ONLY != PROVEN.
TEST PASS != PHYSICAL PASS.
Self-authored producer PASS != independent verification.

## Candidate custody and binding

A candidate is not valid merely because its Git object exists locally.

Before physical proof require one exact identity:

FINAL_SHA == REMOTE_SHA == LOCAL_SHA == BOUND_SHA

Orphaned, detached, unpublished, or checked-out-nowhere commits are not physical-proof candidates until explicitly published/adopted and rebound.

If candidate identity conflicts, phase becomes candidate-state reconciliation; physical execution is forbidden.

## Current late-day state conflict

Durable remote runner:
- branch: runner-recovery/e9b4f15f-20260928
- SHA: e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939
- relation: 12 commits ahead / 0 behind candidate-b-1

Historical/base candidate:
- 34b0a4264bf763bc2a78f761ffba36e47706b2cf

Latest local evidence also reported:
- fixed-but-orphaned commit prefix dfd22bb;
- no durable branch/remote/worktree for that fixed commit at observation time;
- a later Core Freeze check therefore remained BLOCKED;
- dispatcher must publish/adopt that exact fixed candidate or rule it out before writer/reviewer/physical proof proceeds.

This is recorded as a conflict, not silently resolved.

## Source/proof blocker families to keep closed on final bytes

- verifier/key-custody independence;
- N1 stale execute_run1 reference/test path;
- N2 RUN1 -> RUN2 false-green gate;
- transition/result provenance;
- synthesized DONE -> SUCCESS proof;
- truthful exit semantics;
- hardcoded relay proof;
- RUN2 simulation/desimulation;
- expected-hash authority;
- artifact/result identity.

Later source-grounded analysis reported mechanism support for:
- Result -> Verify -> Reconcile -> NEXT_READY;
- B exactly-once/autostart;
- restart/no-replay fail-closed behavior;
- process/resource admission.

These mechanism proofs do not replace certifying physical RUN_1/RUN_2.

## Physical proof rules

Exactly one Physical Mac Owner.

RUN_1 must prove one fresh identity:
- A exactly once;
- real effect;
- exact result/artifact identity;
- task-owned expected hash;
- independent verifier;
- reconcile;
- NEXT_READY;
- B auto-dispatch/start/complete;
- HUMAN_RELAY_COUNT=0;
- FAILED_EXECUTIONS=0.

A failed physical run is sticky.
No retry-to-pass under the same run identity.

RUN_2 may start only after accepted RUN_1 PASS and must prove:
- A persists;
- A does not re-execute;
- A count remains one;
- stale dispatch/result/worker/attempt identities reject;
- B continues legitimately;
- zero human relay.

## Multi-agent lesson

Parallelism is useful only for unique, independent work.

Use a slot router.
One slot = one lane.
Deduplicate before starting.
Reuse unchanged evidence.

When the earliest remaining gate belongs to an exclusive owner:
- other windows park;
- they do not invent edge cases merely to stay busy.

## Queue/UI lesson

A Muse UI session was observed reporting:

Turn-submit backlog full (4)

Therefore:
- do not preload dozens or hundreds of messages into one UI queue;
- queue depth is not a substitute for an external dispatcher;
- a prompt cannot force the UI to keep a turn alive indefinitely.

## Long-session / overnight lesson

A model turn is not a durable scheduler.

"Work for five hours" in a prompt is not a reliable execution primitive.

Long-running autonomy must live outside the model turn:
- headless agent invocation;
- external supervisor;
- durable checkpoints;
- state-change detection;
- relaunch on real trigger;
- token-free waiting between triggers.

For Muse Code, prefer headless muse exec with prompt files and bounded model steps. For unattended trusted-repo work prefer the approval-off posture that keeps the sandbox on; disabling the sandbox is not the default overnight posture.

## NO_REAL_WORK sentinel

When all useful legal work is owner-gated:
- checkpoint WAITING_FOR, NEXT_OWNER, NEXT_ACTION;
- emit exactly NO_REAL_WORK;
- external supervisor waits without model calls;
- relaunch only when a state fingerprint changes.

This is better than watch/sleep inside a model turn.

## Founder-relay lesson

Do not make the founder:
- copy/paste every result;
- refill 30 windows;
- type "continue";
- decide routine routing.

The system should encode:
- current phase;
- exact owner;
- next trigger;
- durable checkpoint;
- self-routing after state changes.

## Model routing

Muse:
- high-throughput read-only source/evidence/adversarial lanes;
- park when no unique lane remains.

Google:
- long-running prep/test/evidence/restart/convergence;
- never accidental second writer.

Windows Central Writer:
- exactly one;
- smallest causal fixes;
- targeted tests;
- exact post-change SHA;
- no unrelated refactor.

Physical Mac Owner:
- exactly one;
- no foreign process takeover;
- no retry-to-pass.

Premium coding/reasoning:
- only for real ambiguity/high-risk critical blocker;
- not routine queue drain.

## Scope

Ledger stays frozen absent explicit retest trigger.
Product Shell stays locked until positive real pilot evidence.
Pilot comes before polish.
Do not let free compute create scope.

## Immediate routing

1. Resolve candidate-state conflict.
2. Publish/adopt or rule out the observed fixed orphan commit.
3. Re-run only invalidated changed-byte review.
4. Establish FINAL_SHA == REMOTE_SHA == LOCAL_SHA == BOUND_SHA.
5. Run one certifying RUN_1.
6. If PASS, run one certifying RUN_2.
7. Core Freeze.
8. Minimum real pilot.

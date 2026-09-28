# Endgame Model / Window Budget Plan — 2026-09-28

Purpose: preserve scarce Opus 4.6 / Supercode capacity for irreversible decisions and use Muse/Google for parallel bounded work.

## Permanent allocation law
- Muse/C2 = broad cheap parallel falsification and evidence design.
- Google/C1 = deterministic source checks, bounded repo fixes, one Central Writer.
- Opus 4.6/C4 = ambiguity arbitration/convergence only; never bulk scanning.
- Codex/C3 = exact fixed-candidate review exactly once per material candidate fingerprint.
- Supercode/rare premium code mode = reserve; use only for a concrete nontrivial blocking repair after Codex or physical-run failure if ordinary Central Writer path cannot safely close it.
- One mutable writer.
- One heavy job per host.
- Available quota is not a reason to repeat completed work.

## Window profile by phase
PRE_CODEX: target 16.
CODEX review: target 8.
RUN_1: target 12, one physical owner.
RUN_2: target 12, one physical owner.
CORE_FREEZE: target 16.
PILOT: target 8-12.

## Opus budget
Use at most two Opus 4.6 calls before Codex:
O1 FINALITY / CAUSAL ARBITER — XHIGH.
O2 PHYSICAL PROOF MINIMALITY — XHIGH.
A third Opus call is allowed only after actual RUN evidence exists and a genuine unresolved semantic conflict remains.

If Opus unavailable, one NO_OPUS_FAST_CONVERGENCE worker is sufficient. Do not queue duplicates.

## Supercode reserve
Before Codex: 0.
After Codex GREEN: keep reserve.
After Codex BLOCKED: use only if defect is genuinely nontrivial and cannot be safely handled by the sole Central Writer with deterministic tests.
After RUN_1/RUN_2 failure: use only for a concrete root-cause packet that remains ambiguous after C1/C2 evidence.

## Muse pre-Codex allocation
Use 16 distinct read-only tasks; one task per window, one pass. Never use old 65-96 router.
1 returned-result policy conformance
2 result->verify->reconcile truth
3 NEXT_READY vs dispatch/start
4 exactly-once identity
5 stale-worker recovery
6 crash after result before verify
7 crash after reconcile before successor
8 cross-process locking
9 state-copy drift
10 provider failure isolation
11 human-gate parking
12 cost/budget admission
13 context-pack staleness
14 proof invalidation/staleness
15 RUN_1 witness design
16 RUN_2 no-replay witness design

## Stop conditions
FAMILY_COMPLETE -> do not repeat.
BLOCKED_OTHER_OWNER -> route away.
Gate changes -> change phase.
Real run evidence exists -> stop template review and inspect actual instance.

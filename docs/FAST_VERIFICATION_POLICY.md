# Fast Verification Policy

Status: REQUIRED MASTER RULE for Courier development and product milestones.

Purpose: minimize wall-clock verification time without weakening evidence quality.

## Core principle

Use the smallest sufficient verification first. Verification cost must be proportional to change risk.

`TARGETED_TESTS_FIRST = YES`

`FULL_REGRESSION_ONCE_PER_MILESTONE = YES`

`DUPLICATE_FULL_REGRESSION = FORBIDDEN`

`HEAVY_JOB_LIMIT = 1`

`UNCHANGED_PROVEN_STATE = REUSE`

`STALLED_TEST = ISOLATE_NOT_WAIT`

`NO_NEW_PHASE_WHILE_PREVIOUS_ACTIVE = YES`

`RESUME_FROM_LAST_PROVEN_STATE = YES`

## Proven incident and recovery — 2026-09-06

A real Prompt-1/Prompt-2 overlap produced four stranded/duplicate unittest processes. The recovery inspected the exact unittest processes, terminated the four stale/duplicate processes, and returned execution to a single bounded work path. The recovery report recorded `DUPLICATE_TEST_PROCESSES_CLEANED=YES`, `STALLED_TESTS_ISOLATED=4`, `TARGETED_TEST_POLICY_ACTIVE=YES`, and `FULL_REGRESSION_COUNT_THIS_RUN=0`.

This incident is now a permanent operational lesson, not a one-off workaround.

### Proven recovery pattern

`DETECT ACTIVE TESTS -> IDENTIFY DUPLICATE/STALE RUNS -> TERMINATE ONLY THOSE RUNS + CHILDREN -> HEAVY_JOB_LIMIT=1 -> RUN SMALLEST TARGETED TEST -> REUSE UNCHANGED PROOF -> CONTINUE PRODUCT WORK -> ONE FINAL REGRESSION ONLY IF REQUIRED`

Do not use broad `kill` behavior when exact process identity can be determined. Passive Courier daemons and unrelated processes must remain untouched.

A new prompt, account, model, terminal, or phase MUST NOT create a second heavy regression merely because the previous UI context changed.

## Default verification ladder

1. Identify the exact changed module or behavior.
2. Run the smallest directly relevant test method or class.
3. If it passes, run the relevant test module only when that adds useful evidence.
4. Continue the implementation milestone without launching a full suite.
5. Run one full regression only at the final coherent milestone boundary, or earlier only when a high-risk core change cannot be covered sufficiently by targeted evidence.

## Duplicate and stale process rule

Before launching a heavy test or full regression, inspect whether another heavy regression is already active. Never start a second full regression for the same repository state.

If duplicate or stale test processes exist, keep at most the single legitimate progressing run and terminate only duplicate/stale test processes and their children. Do not terminate unrelated passive Courier daemons.

If no legitimate progressing heavy test remains, start only the smallest required targeted verification. Do not automatically replace four stale full-suite runs with one new full-suite run.

## Bounded test rule

Long tests must have a bounded runtime and progress visibility sufficient to identify the current test or module. A test that stops making observable progress is classified as stalled. Do not repeatedly restart the whole suite.

Recovery sequence:

`FULL SUITE -> IDENTIFY HANGING TEST -> TERMINATE STALE RUN -> REPRODUCE HANGING TEST ALONE -> FIX SMALLEST GENERAL DEFECT -> TARGETED PROOF -> ONE FINAL REGRESSION`

Waiting without new evidence is not verification. Once a run is demonstrably stalled, additional blind waiting has zero information gain.

## Fingerprint/evidence reuse

When the relevant code fingerprint and dependency surface are unchanged, reuse a previous verified PASS instead of rerunning the same verification merely because a session, model, account, terminal, or prompt changed.

`SAME_RELEVANT_FINGERPRINT + VERIFIED_PASS = REUSE`

A quota interruption, account switch, crash, or operator handoff is not a reason to rerun already-proven unchanged tests.

## Practical unittest acceleration

Prefer selecting exact modules/classes/methods rather than `python -m unittest discover` during normal development. Use `-k` where supported to select matching tests, `-f/--failfast` for diagnostic runs where the first failure is sufficient, and duration reporting where supported by the installed test runner to identify slow tests. Test cases should remain runnable in isolation.

Do not use fail-fast as final proof when the acceptance contract requires the entire selected suite to pass; it is primarily a diagnostic acceleration tool.

## Phase overlap rule

Prompt/phase N+1 must not start a duplicate heavy verification while Prompt/phase N still has active heavy work. The next phase must first reconcile the existing active process, reuse its evidence if valid, or classify and terminate it if stale/duplicate.

`NEW_PHASE -> CHECK ACTIVE_HEAVY_WORK -> REUSE/WAIT_IF_PROGRESSING OR CLEAN_IF_STALE -> THEN CONTINUE`

This check is mandatory before a new phase launches expensive or long-running verification.

## Product-first rule

Courier is infrastructure. Do not spend product sessions repeatedly re-proving unchanged Courier internals. Once a demonstrated Courier blocker is minimally repaired and sufficiently verified, return immediately to product progress.

## Final milestone proof

At a coherent milestone boundary:

- confirm no duplicate full regression is running;
- execute at most one required Courier full regression;
- execute at most one required product regression;
- persist exact counts, fingerprint, IDs, blocker state, and canonical YES/NO handoff fields.

The goal is not fewer tests at any cost. The goal is fewer redundant tests, faster diagnosis, bounded waiting, and equivalent or stronger evidence per minute.

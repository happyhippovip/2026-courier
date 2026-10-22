---
name: courier-orchestrate
description: Orchestrates Courier Symphony development from current repo truth. Use for morning sync, overnight planning, result harvest, window custody, lane activation, and next-step assignment without changing the locked V1 architecture.
---

# Courier Orchestrate

## First read

Read:
1. `AGENTS.md`
2. `docs/V1_RULE_0.md`
3. `docs/V1_PRODUCT_QUALITY_BAR.md`
4. `docs/V1_ORCHESTRATION_PLAYBOOK.md`
5. `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
6. `docs/NEXT_CHAT_HANDOFF.md`
7. newest relevant GitHub Issue #54 rules
8. CURRENT `integration/v1`
9. `docs/v1/INTEGRATION_LOG.md`

Never trust a historical SHA without verifying it.

## Default mode

Read-only orchestration.

Do not edit product source, create a writer lane, merge, or perform consequential external actions unless the user explicitly assigns that action and it is compatible with the six-lane model.

## Determine requested mode

Infer one of:

- MORNING_SYNC
- NIGHT_PLAN
- HARVEST
- WINDOW_CUSTODY
- LANE_ACTIVATION
- SECURITY_REVIEW
- GENERAL_ORCHESTRATION

## Common steps

1. Verify current trunk SHA.
2. Identify official L1-L6 branches/PRs.
3. Identify the first unproven V1 gate.
4. Separate durable GitHub truth from local/session liveness.
5. Use local artifacts/checkpoints only if actually available.
6. Deduplicate old/historical findings.
7. Do not resurrect 30x/100x/NIGHT/YOLO writer swarms.
8. Prefer deep queues + bounded concurrency.
9. If host pressure/EMFILE is present, start no new local subagents/heavy workflows.
10. Apply window custody before recommending /clear or close.

## MORNING_SYNC

Produce:
- CURRENT_HEAD
- ACTIVE_WRITERS
- ACTIVE/KNOWN_WORKFLOWS if evidence is available
- COMPLETED_OVERNIGHT_RESULTS
- REAL_BLOCKERS
- DUPLICATES_REMOVED
- WAIT_FOR_LANE
- SAFE_WRITER_ACTIVATION_ORDER
- SAFE_WINDOWS_TO_CLEAR/CLOSE only when custody is proven
- exact next prompts/actions

## NIGHT_PLAN

Design bounded work.

Prefer:
- one official writer per eligible lane;
- read-only Muse/Antigravity factories for future lanes;
- no duplicate scope;
- staged investigator -> verifier waves;
- explicit artifact/checkpoint paths;
- a finite queue;
- no artificial waiting or no-op loops.

On Mac, keep live child concurrency conservative because Courier has prior EMFILE/resource-pressure evidence.

## HARVEST

Read completed artifacts/checkpoints.

For every finding classify:
- PROVEN
- REAL_BLOCKER
- DUPLICATE
- SUPERSEDED
- WAIT_FOR_<LANE>
- DEFER_AFTER_EXE

Map actionable items to exactly one L1-L6 owner.

Do not convert read-only scouts into writers.

## WINDOW_CUSTODY

Use `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`.

Unknown => not safe to clear/close.

Never clear/close an active workflow or writer with undurable work.

## LANE_ACTIVATION

Activation follows evidence gates, not available credits or idle windows.

Current route:
ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY.

Return:
- lane
- prerequisite
- evidence that prerequisite is met/not met
- model/effort recommendation
- exact owned scope
- collision risks
- L1 merge gate


## SECURITY_REVIEW

A bounded read-only review mode of this **existing** orchestration skill, not a
new runtime agent, worker lane, scheduler, or permission grant. Inspired by
[claude-howto's read-only reviewer](https://github.com/luongnv89/claude-howto/blob/main/04-subagents/secure-reviewer.md)
and [hook guidance](https://github.com/luongnv89/claude-howto/tree/main/06-hooks);
do not copy or install external scripts.

1. Verify the current `integration/v1` SHA, relevant open PRs, active owner and
   exact file scope. If an owner already has the finding, mark DUPLICATE and stop.
2. Stay read-only: use indexed search, known-file reads and available repository
   APIs. Never edit, commit, start providers, run untrusted code, modify hooks,
   install plugins, change permissions, start new processes, or spawn a reviewer
   by default. Follow `.agents/rules/NO_GREP_FAMILY.md`.
3. Do not open secret values, `.env`, credential stores, private family/personal
   data, raw command transcripts or unrelated logs. Do not include sensitive
   source content in the review report. If evidence requires protected data,
   report NEEDS_AUTHORIZED_REVIEW without accessing it.
4. Inspect only relevant trust boundaries:
   - **Authority:** parent/child lease binding, epoch, holder and stale-token
     rejection at the real side-effect boundary.
   - **Cost:** absent, non-finite or unknown estimates must block **before**
     dispatch/adapter execution; zero-cost must be demonstrated, not presumed.
   - **Evidence:** worker outcome, journal event, input/output fingerprint
     and verifier must agree; fabricated, missing or foreign FINAL evidence
     cannot be promoted to VERIFIED.
   - **Host/recovery:** no duplicate dispatch on resume; respect resource
     pressure and single-writer ownership.
5. For provider-native hooks and permission rules, distinguish a *notification*
   (e.g. `PENDING_POLICY_CHECK`) from an enforced denial. Never call a bridge
   callback or a passing check an enforced gate without a negative probe that
   proves the forbidden side effect did not happen. Draft a bounded deterministic
   negative test for the official owner; do not perform risky live actions.
6. Permission-friction reductions are restricted to explicitly trusted,
   project-scoped read-only Markdown paths in the native permission system
   **after** current path/scope verification. No global blanket allow, no
   secrets access, no escalation to Write/Bash/network/provider/merge/spend,
   and no bypass of real human gates. This skill grants no permissions.
7. Session checkpoint/rewind can aid an individual Claude session; it does
   **not** replace Courier's durable journal, task identity, owner lease or
   evidence of actual execution.
8. Provide only actionable, deduplicated findings. Route any code change or
   targeted test implementation to its existing L1-L6 owner and retain L1's
   integration/merge gate. No independent agent promotion.

Output for each nonduplicate finding:
- CURRENT_HEAD, FILE/FUNCTION, EXISTING_OWNER/PR, SEVERITY
- EXPECTED_DENIAL_OR_INVARIANT and OBSERVED_EVIDENCE (with source reference)
- SMALLEST_NEGATIVE_TEST, PROPOSED_MINIMAL_FIX, OWNER_LANE
- STATUS = PROVEN | SUSPECTED | DUPLICATE | BLOCKED
- SAFETY = READ_ONLY, COST = 0 EUR (only if actually verified)

Never label a hypothetical negative test as PASS or claim live enforcement
without observing the real side-effect boundary.

## Subagents

Default: zero.

For a broad read-only orchestration question, at most two independent background subagents may be used when the host is healthy and they cover non-overlapping evidence.

No recursive subagents.
No parallel product writers.


## Repository search safety

Persistent workspace rule: `.agents/rules/NO_GREP_FAMILY.md`.

For Courier repository discovery, do not invoke `grep`, `egrep`, `fgrep`, `git grep`, `rg`, or `ripgrep`.
Prefer Antigravity/editor indexed search, direct known-file reads, or GitHub code/file APIs.
If a grep-family task is already running, cancel it and do not retry it.

## Persistence

If the user explicitly asks to make a new orchestration rule durable:
- prefer updating the canonical playbook/skill/template via a normal GitHub branch/PR;
- add a concise Issue #54 continuity note for major rule changes;
- do not store transient PID/window liveness as canonical repo truth.

## Final principle

Optimize for:
- less owner repetition;
- fewer duplicated scans;
- fewer resource incidents;
- earlier discovery of correctness failures;
- faster safe lane activation;
- finished Windows V1.

Do not optimize for looking busy.

## Long-running owner-time mode

When Dennis asks for one window that should keep doing useful Muse work without repeated manual prompting:

- do not fake duration with a giant prompt;
- do not ask him to queue the same prompt hundreds of times;
- if `.agents/skills/courier-night-loop/SKILL.md` exists in the current checkout, prefer `/loop 5m /courier-night-loop`;
- each wake must advance a new evidence fingerprint or idle honestly;
- Windows Muse sessions do not have peer-session messaging, so do not depend on many Windows Muse terminals coordinating with one another;
- when true parallel read-only work is warranted, prefer a bounded Antigravity subagent fan-out from one control-room session.

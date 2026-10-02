# Cost-Safe Gate Transition Policy — 2026-09-28

Status: CANONICAL / OVERRIDES OLDER PROMPT-SPECIFIC GATE LOOPS

Purpose:
Prevent multiple CLI/model windows from repeatedly paying to rediscover the same phase gate.

## Core law

A gate report is not a durable gate transition.

PRE_CODEX_READY=YES becomes authoritative for cross-window/cross-host orchestration only when the exact gate fingerprint is durably recorded and the final candidate is durably resolvable.

## Gate fingerprint

For PRE_CODEX use:

GATE_FINGERPRINT =
PRE_CODEX
+ FINAL_SHA
+ BASE_SHA
+ exact changed-file set
+ 12-case evidence fingerprint
+ targeted-test result fingerprint
+ SKIPPED_COUNT
+ diff-check result
+ blocker state

Same fingerprint = same gate work.
Do not re-review it in another window merely because provider/session/account/host changed.

## State machine

OPEN
-> REPORTED
-> DURABILITY_PENDING
-> VALIDATING
-> READY
-> CONSUMED / NEXT_PHASE

REPORTED is not READY.

## Durable candidate requirement

A FINAL_SHA used for a cross-host gate must be resolvable from one of:
1. canonical remote repository ref/commit;
2. explicitly referenced durable candidate bundle with cryptographic hash;
3. another canonical durable store named by the gate record.

A SHA visible only in one local session/working copy is DURABILITY_PENDING.

Do not send many reviewers to rediscover a non-durable local SHA.

## Single gate owner

For each new GATE_FINGERPRINT:
- exactly one GATE_VALIDATION_OWNER may validate it;
- all other workers reuse the durable verdict;
- if validation is already claimed, other workers skip the gate family and take unrelated READY work or IDLE.

## Result cache

Persist:
GATE_NAME=
GATE_FINGERPRINT=
FINAL_SHA=
DURABLE_SOURCE_REF=
VERDICT=
VALIDATED_AT=
VALIDATED_BY=
NEXT=
INVALIDATION_TRIGGER=

If fingerprint is unchanged, RESULT_REUSE_FIRST is mandatory.

## Admission control

Before admitting model-powered work:
1. inspect current gate state with a cheap deterministic read;
2. if this task family is already READY/CONSUMED for the same fingerprint, do not admit another model worker to that family;
3. if DURABILITY_PENDING, admit at most one persistence/bridge owner;
4. if VALIDATING, admit no duplicate validators;
5. if no other READY work exists, TRUE_IDLE without model-powered analysis.

This rule exists specifically to avoid user cost from duplicate gate discovery.

## PRE_CODEX transition

If PRE_CODEX fingerprint is durably READY:
- close PRE_CODEX work family;
- record NEXT_GLOBAL=CODEX_HIGH_ONCE;
- Windows workers may take other non-duplicate authorized work;
- Mac/Muse workers may take legal POST_PRE_CODEX_PREP;
- do not repeat PRE_CODEX validation.

If FINAL_SHA/evidence fingerprint changes:
invalidate only candidate-sensitive cached gate evidence and create one new validation claim.

## Safety

Do not mark READY merely because a worker printed PRE_CODEX_READY=YES.
NO_EVIDENCE_NO_PASS remains authoritative.

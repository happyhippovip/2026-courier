# Courier Large Work Packages — 2026-09-26

Purpose: give long-run wall slots substantial, non-duplicative work that can consume 2–4 useful hours without requiring human relay.

All packages default to READ_ONLY_REPORT unless durable coordination grants exact writer ownership.

## L1 — Final Candidate Evidence Reconciliation

Goal:
Find the newest descendant of candidate-b-1 that is plausibly the final five-file candidate and reconcile exact changed files, ancestry and executed test evidence.

Required output:
CANDIDATE_SHA
BASE_SHA
CHANGED_FILES
EXACT_FIVE_FILE_SCOPE
EXECUTED_TESTS
PASSED
FAILED
SKIPPED
CONTRADICTIONS
READY_FOR_CODEX_HIGH
BLOCKER

Do not promote candidate-b-2.

## L2 — Twelve-Case Acceptance Matrix

Map each required final invariant to:
- implementation path
- test path
- executed evidence
- stale evidence
- missing evidence

Required cases:
1 task-owned expected hash survives Goal->Claim->Pending Verification
2 correct server bytes PASS
3 wrong server bytes FAIL
4 worker expected hash rejected
5 worker omission cannot bypass task expectation
6 missing task expectation remains legacy, not exact-content
7 malformed/ambiguous target FAIL
8 identical replay ACK, including reload where relevant
9 changed status not duplicate success
10 changed worker not duplicate success
11 changed attempt/dispatch rejected
12 changed artifact result not duplicate success

## L3 — Duplicate / Replay / Lost-ACK Deep Audit

Trace all result-submit/retry/reload paths.

Prove or flag:
- exact canonical replay identity
- status changes
- worker changes
- attempt changes
- dispatch-generation changes
- artifact-result changes
- persistence/reload behavior
- lost ACK and client retry
- stale result after newer truth
- FAILED execution cannot become fake clean PASS

## L4 — Restart Durability + Crash Window Map

Trace durable state across:
- before result persistence
- after result persistence
- before verification
- after verification
- before reconciliation
- after reconciliation
- before B eligibility
- after B dispatch

For each crash point state:
WHAT_SURVIVES
WHAT_REPLAYS
WHAT_MUST_NOT_REPLAY
FAIL_CLOSED_BEHAVIOR
EXISTING_TEST
MISSING_TEST

## L5 — Goal-to-Ledger Identity Trace

Trace one logical task through:
GOAL
-> CONTRACT
-> TASK
-> CLAIM
-> ATTEMPT
-> DISPATCH
-> EXECUTION
-> RESULT
-> ARTIFACT
-> VERIFY
-> RECONCILE
-> NEXT READY

Find:
- identity gaps
- mutable fields used as identity
- stale overwrite opportunities
- missing durable binding
- unproven transitions

## L6 — Wall 1..37 Scheduler Design Audit

Do not implement yet.

Reconcile existing:
- resource guard
- SessionWorkBudget
- SessionBudgetLedger
- process ownership
- claim/lease mechanisms
- result-driven continuation
- runtime/slots conventions

Produce the smallest path from current code to:
REQUESTED 1..37
ADMITTED
ACTIVE
WAITING
GUARDED
RESERVED_INTERACTIVE
IDLE

Keep heavy jobs separate from logical slots.

## L7 — Resource / Thermal / Process Ownership

Audit Mac + Windows assumptions statically.

Find:
- unbounded subprocesses
- timeout without tree cleanup
- stale PID reuse
- broad process killing
- duplicate heavy admission
- missing wait/poll confirmation
- process claims without create-time identity
- resource guard bypass

Never treat mocked Windows taskkill as physical Windows proof.

## L8 — Cross-Platform Portability

Trace platform-sensitive:
- paths
- shell commands
- encoding
- CRLF/newlines
- process groups
- PID handling
- temp directories
- file locks
- PowerShell/bash assumptions
- Mac-only tests
- Windows-only behaviors

Classify each:
PROVEN_PORTABLE
PLATFORM_BOUND_INTENTIONAL
NEEDS_TEST
BUG_RISK

## L9 — Result Harvester / Human-Relay Removal

Map how current reports/results are returned and where the human still acts as message bus.

Design-only output:
- current return surfaces
- dedupe key
- evidence ingestion path
- contradiction handling
- next-READY recompute
- slot refill event
- minimal truthful human summary

No new orchestration architecture unless existing primitives cannot satisfy the requirement.

## L10 — Product Truth / Grandma Test

Read current dashboard/studio/product docs.

Find every place where a nontechnical user could misunderstand:
- reported vs verified
- active vs requested capacity
- idle vs broken
- guarded vs unavailable
- result received vs done
- candidate source vs loaded runtime

Propose plain-language copy and icon use.
Do not build UI before RUN_2.

## L11 — Crew Role Dedup / Growth

Audit existing role prompts/reports.

Produce:
- current unique roles
- duplicates/overlaps
- missing recurring evidence roles
- roles to merge
- roles to retire
- maximum useful parallel read-only spread before duplication dominates

Goal:
larger crew with less duplicated thought.

## L12 — Pilot-Readiness Evidence Gap

Without marketing or invented pricing, map what must be true before a first friend/pilot can safely use Courier.

Cover:
- setup
- permissions
- data boundaries
- deletion
- failure explanation
- restart
- proof card
- resource safety
- money gates
- human relay count

Keep it NON_CODE_PREP until core proof passes.

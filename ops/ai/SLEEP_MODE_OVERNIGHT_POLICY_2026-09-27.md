# Courier Sleep Mode — Overnight Wall Policy — 2026-09-27

Status: ACTIVE OVERNIGHT OPERATING POLICY

## Correction

A prompt cannot guarantee that one AI/CLI session will keep actively working for 5 or 10 hours.

A session may stop early because of:
- provider/session limits
- model deciding the scoped task is complete
- rate limits
- shell/tool failure
- context/runtime failure
- no safe READY work
- resource guard

Therefore Courier overnight success is defined as **wall continuity**, not "every single window runs for N hours".

## Sleep-mode goal

The user should be able to go to sleep while a diversified wall continues useful work with minimal relay.

Target:
- up to 10 hours wall-clock
- many independent read-only slots
- no human prompt after every task
- durable checkpoint after each package
- stale-context rotation
- no duplicate work
- no source-writer collisions
- no heavy-load stampede

## Hard truth

Do not say:
"this window will work for 5 hours"

Say:
"this window is instructed to continue for up to N hours, but may stop earlier for real stop conditions."

## Pre-sleep setup

1. Keep Windows Antigravity Central Writer as sole final-candidate source writer.
2. All other overnight lanes default READ_ONLY_REPORT.
3. Start fresh contexts where possible.
4. Muse fresh-start lifecycle: checkpoint -> /clear or new session -> muse --yolo only when explicitly chosen by user -> load overnight prompt.
5. Google/Antigravity CLI: fresh context if stale -> load overnight prompt.
6. Leave a small interactive reserve unused.
7. Do not open more physical windows after the host becomes laggy.
8. Prefer smooth 8-12 active light sessions per host over a laggy larger set.
9. Current MAX_HEAVY_JOBS=1 per host unless newer proven policy says otherwise.
10. Do not touch live physical proof processes until the exact final candidate is ready.

## Overnight slot behavior

Each slot:
- claims one logical ID;
- selects one unowned role family;
- works on LARGE packages;
- after completing a package, immediately chooses the next unowned safe package;
- checkpoints durable findings;
- clears/rotates stale context when useful;
- continues without asking the human;
- stops only on a real stop condition.

## Role families

1. final-candidate/test evidence
2. 12-case acceptance matrix
3. duplicate/replay/lost ACK
4. trusted artifact/hash chain
5. restart durability/crash windows
6. auto-B eligibility/dispatch
7. claim/lease concurrency
8. failure semantics
9. resource/process safety
10. portability
11. stale truth/branch reconciliation
12. result harvester / Ledger gaps
13. product truth / Grandma test
14. update/signing/crypto-readiness (non-critical-path, read-only)
15. crew dedup / next useful roles (minority capacity)

## Stop conditions

A slot may stop early only for:
- NO_SAFE_READY_WORK
- PROVIDER_LIMIT
- RATE_LIMIT
- TOOL_OR_SHELL_BLOCK
- RESOURCE_GUARD
- OWNERSHIP_AMBIGUITY
- COST_OR_QUOTA_GUARD
- HUMAN_MONEY_PERMISSION_GATE
- REPEATED_STATE_NO_PROGRESS

## When a slot stops early

Do not fake continuity.

It must leave:
- SLOT
- ROLE
- PROVEN
- OPEN
- BLOCKED
- DO_NOT_REPEAT
- NEXT_EXACT_ACTION
- STOP_REASON

The remaining wall continues.

## Success metric

Overnight success is:
- more verified evidence
- fewer unknowns
- no duplicate source writes
- no human relay
- host still healthy in the morning

Not:
- all windows visually busy for 10 hours.

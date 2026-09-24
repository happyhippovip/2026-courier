# Courier Execution Masterplan — 2026-09-24

Status: coordination and execution plan. This document does not replace runtime truth, the handoff ledger, or human approval gates.

Related handoff:
- `docs/plans/CHATGPT_HANDOFF_2026-09-24.md`

## 1. Purpose

Courier should keep useful work moving across Mac, Windows and later Cloud without requiring the user to babysit every worker, while avoiding duplicate work, unsafe parallel writes, false DONE states and context loss.

The design principle is:

`READ STATE -> CLAIM SAFE SCOPE -> WORK -> MICRO-VERIFY -> PERSIST RESULT -> NEXT SAFE TASK`

A worker should not become idle merely because one small step completed. It should take the next safe task in its assigned scope. It must not manufacture busywork.

## 2. Source-of-truth order

When sources disagree, do not silently merge them.

1. Canonical runtime state for active goals/tasks/external effects
2. Valid handoff ledger + hash/history + writer ownership
3. Git branch/commit state and tested artifacts
4. Project documentation / plans
5. Chat history and screenshots

A chat message is never sufficient proof that runtime state, GitHub persistence or an external effect succeeded.

## 3. Existing program order

Keep the existing P0-P6 sequence:

- **P0 — Bestand / Zuständigkeit:** establish repo, branch, SHA, dirty state, ledger revision/hash, active writer, runtime/process inventory and access.
- **P1 — Ledger / Wiederaufnahme:** prove a cold session can reconstruct goal, evidence, writer, blocker and next action without old chat.
- **P2 — Abschluss / Fortsetzung:** fix evidenced false-DONE / stuck-ACTIVE semantics minimally and verify with focused tests.
- **P3 — Echter Betriebsnachweis:** one isolated real goal, at least two real workers, at least ten acceptable completions, interruption/resume, no duplicate external effect, no leaked job processes, honest DONE/CLEAN_IDLE.
- **P4 — Kleiner Pilot:** one real small customer flow end-to-end.
- **P5 — Produkterweiterungen:** only separately accepted packages after the core proof.
- **P6 — Wirtschaftlichkeit:** pricing based on measured provider, infrastructure, support and failure costs.

Do not jump to P4-P6 to avoid unresolved P0-P3 work.

## 4. Worker operating model

Every worker has:

- `agent_id`
- `task_id`
- `scope`
- `state`
- `updated_at`
- `proof_type`
- `proof_ref`
- `last_result`
- `next_action`
- `blocker`

Recommended states:

- `QUEUED`
- `WORKING`
- `RESULT_READY`
- `VERIFYING`
- `WAITING`
- `BLOCKED`
- `DONE`

Normal loop:

`WORKING -> RESULT_READY -> VERIFYING -> PASS -> next task -> WORKING`

`WAITING` is valid only for a real dependency, human gate, provider limit, schedule or lack of any safe executable task.

`BLOCKED` requires a named blocker, evidence and owner.

## 5. Micro-verification

Do not launch one verifier LLM per worker.

Use one lightweight supervisor or deterministic verification path that wakes only on `RESULT_READY`.

Choose the smallest meaningful proof for each result:

- expected file exists
- expected diff exists
- expected test returns exit code 0
- expected artifact exists
- expected runtime state exists
- expected process is alive
- expected hash/mtime changed
- expected ledger/history event exists

Do not re-run a full project analysis after each small task.

If verification fails, return the same task to the worker with the missing proof. Do not mark DONE.

## 6. Scheduler rule: useful work, not busywork

When a task completes, the scheduler should:

1. read current scope and ownership,
2. find the next dependency-ready task,
3. avoid files/scopes owned by another active writer,
4. claim exactly one independent task,
5. dispatch it,
6. continue until a true gate is reached.

More workers do not automatically mean more progress. Never start additional workers only to increase activity.

Parallel work is allowed only for independent scopes with explicit ownership.

## 7. Persistence / “storage worker” model

Use a lightweight archival step after accepted results. This is not a second runtime authority.

The archive/storage worker stores only concise, reconstructable evidence:

- task ID and scope
- input/precondition reference
- exact result summary
- proof reference
- Git commit/path when applicable
- runtime/ledger reference when applicable
- next action
- blocker/owner if blocked

Do not store raw full chats when structured evidence is enough.

The storage worker must never invent that something was saved. Persistence is confirmed only by a concrete returned path, URL, commit SHA, ledger revision or equivalent read-back proof.

If the current worker lacks GitHub/Cloud access, it must report:

`PERSISTENCE_PENDING`

with:
- intended destination,
- exact content/artifact reference,
- reason access is unavailable,
- designated persistence owner.

It must not claim “saved to GitHub”.

## 8. GitHub policy

GitHub is for durable code, tests and sanitized project documentation, not raw runtime truth.

Rules:

- no secrets, tokens, private account data or raw personal chats
- no automatic merge to `main`
- small scope-specific commits
- do not overwrite foreign uncommitted work
- check branch, HEAD and writer ownership before writes
- prefer additive docs/branches for planning material
- record exact commit SHA after successful persistence

A worker without GitHub access prepares a persistence packet; a GitHub-capable worker performs the write and reports the resulting commit.

## 9. Mac execution scope

Current developer-wall target:

- 64 Muse
- 6 Anti-Gravity
- Muse command: `muse --yolo`
- AG command: `HOME=/Users/user/.gemini_alt agy`
- visible target: Muse 8x8, AG 2x3

Keep the two-step wall design:

1. `WALL-AUFBAUEN` — identify/create only intended wall slots and arrange them
2. `WALL-STARTEN` — start the expected process exactly once in each verified slot

Do not adopt arbitrary idle Terminal windows.

Do not use Terminal `busy` alone as duplicate-start protection.

Desired restart flow:

`REBOOT -> WALL-AUFBAUEN -> verify slots -> WALL-STARTEN`

Do not auto-start all provider sessions at login.

Future configuration should support 32/64 Muse counts with the same core mechanism.

Future background mode should reuse the same task/slot identity model rather than requiring all workers to remain visible in Terminal windows.

The Mac worker may continue independent Mac work while Windows works in parallel.

## 10. Windows execution scope

Windows should independently inventory:

- checkout/branch/HEAD/dirty state
- ledger references and ownership
- services/processes/restart behavior
- path semantics
- subprocess/shell behavior
- locks
- encoding
- temporary files
- shutdown/restart/recovery
- Windows-specific tests and parity gaps

Do not edit Mac Wall code.

Shared ledger/motor scopes stay read-only while another writer owns them.

## 11. Cloud / Docker later

Cloud/Docker is a later execution environment, not a reason to redesign the core today.

When introduced, it should reuse:

- task IDs
- claims
- worker states
- micro-verification
- persistence packets
- resume semantics
- writer ownership

The first Cloud/Docker milestone should be a small isolated worker and persistence proof, not an immediate migration of the entire wall.

## 12. Human gates

Workers may autonomously perform safe, reversible work in their confirmed scope: reads, focused tests, backups, isolated file changes, validation and scope-safe commits.

Human approval remains required for:

- unknown/destructive process termination
- deleting unknown or foreign data
- overwriting foreign uncommitted work
- destructive Git operations
- production/main merges
- public publication of new sensitive/unreviewed material
- money, payments or irreversible external actions
- secrets/credential changes
- actions outside confirmed writer scope

A human gate must include:
- reason
- evidence
- safe alternative
- exact next action after approval

## 13. Customer-facing status

Do not expose a vague internal runner label like “Standby” as the product truth.

Customer-facing status should map to Courier state:

- **Working** — a task is executing
- **Checking** — smallest proof is being verified
- **Waiting** — a real dependency is pending
- **Blocked** — intervention is required
- **Done** — acceptance criteria are satisfied

An underlying provider UI showing “Standby” does not prove the Courier task is idle.

## 14. Resume contract

Before any worker/runner stops, it should persist or emit:

- `RESUME_STATE`
- `NEXT_ACTION`
- `NEXT_COMMAND` when appropriate
- `EXPECTED_PROOF`
- `WHY_SAFE`

A new session reads these plus the current ledger/runtime/repo state, verifies they still match, and continues from the confirmed next action rather than replanning from zero.

## 15. Immediate execution focus

For the current work period:

1. Make the Mac wall state reconstructable and reboot-safe.
2. Avoid destructive cleanup until sessions/tasks are identified.
3. Re-establish the intended 64+6 wall without duplicate starts.
4. Run P0 and resolve repo/ledger/writer mismatches.
5. Keep Windows on independent Windows-specific scopes.
6. Implement/reuse micro-verification and reliable resume before scaling worker count.
7. Continue P1 -> P2 -> P3.
8. Only after P3, run one small P4 customer pilot.
9. Use P3/P4 measurements for P6 economics.

## 16. Completion principle

“Done” means acceptance evidence exists and the next session can reconstruct what happened.

“Workers are active” is not a completion criterion.
“Many agents are running” is not a completion criterion.
“A file exists” is not a completion criterion.
“A chat said it worked” is not a completion criterion.

Courier is successful when verified work survives handoffs, resumes safely, avoids duplicate external effects and moves to the next permitted task without human babysitting.

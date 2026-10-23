# Google Antigravity Mac — Scoped Autonomous Work Plan
**Public workflow specification · 23 October 2026 · Happy Hippo VIP × Courier Symphony**

> **Status: documentation only.** This page does **not** enable an automation, launch an agent, authorize edits, create a lease or guarantee uninterrupted operation.
>
> **23 October runtime correction:** The user's existing Mac session reported an active Goal and an existing 30-minute wake-up timer but **no separate `/schedule` command in that conversation**. Do not start a second timer or Goal. Use the revised [Google Mac Auto-Resume Prompt V2](./GOOGLE_MAC_AUTO_RESUME_PROMPT_V2_2026-10-23.md), which is the copy-paste command for this scenario.

## Purpose

Give the existing Google Antigravity Mac engineering verifier a repeatable, low-interruption workflow. Do **not** create a second product writer or replay completed acceptance work.

Google Antigravity documents the following features:

- `/goal`: long-running evidence-based task completion within the current session;
- `/schedule`: may be documented in other versions or contexts, but is **not available as a separate command in the pictured session**; the existing timer is the relevant wake-up mechanism;
- subagents: independent focused analysis;
- workspace rules and agent skills: reusable instructions;
- JSON lifecycle hooks: carefully scoped execution policy enforcement;
- scheduled sidecars: longer-lived jobs managed by Antigravity, **separate from conversation timers**.

These features are capability descriptions, not proof of availability or active configuration for a given user account. Verify installed version, active tasks and billing before use.

## Agent ownership

**Google Antigravity Mac = independent integration auditor and product verifier.**

- Read-only review of current GitHub PRs and available candidate patches;
- focused negative tests, on an isolated disposable test tree where authorized;
- synthetic A→B→C journal/receipt verification;
- regression and macOS-specific resource observations;
- accurate L1 handoff evidence;
- offline demo checks with no provider calls.

**Not authorized by this plan:** code edits in another lane, integrations into `integration/v1`, remote merges, arbitrary shell commands with uncertain cost, task-scheduler changes, cloud agents or public posting.

## Single-session operating order

1. **Inventory:** inspect current Antigravity app/version, active tasks, current Git/CI, latest checkpoint, and owned scopes. Deduplicate any existing schedule. Do not reopen a completed queue.
2. **Define one bounded goal:** independently validate a specific new commit or integration candidate against concrete proof obligations. If there is no new commit/event or testable gap, remain quiet.
3. **Use two lightweight read-only subagents at most on this Mac:** e.g., receipt/ledger proof and cross-host claims. Avoid concurrent heavyweight pytest runs.
4. **Produce actual evidence:** commit SHA, test name, exit code, synthetic vs real-provider provenance, remaining blocker and owner.
5. **Checkpoint:** after significant work, store evidence in a previously approved private destination; do not include secrets or personal information.
6. **Use the existing single wake-up mechanism:** when a timer/watch is already active, neither duplicate it nor try an unsupported `/schedule` command. Only compare new PR/CI evidence on wake-up.
7. **Stop:** stop at the specified expiry, invalid lease, resource pressure, quota exhaustion or uncertain cost. Never claim unattended operation without a verified scheduler.

## Resource and safety contract

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

The Mac is resource-constrained, so avoid spawning many agents or parallel test suites. No secret collection and no publishing private project-memory material.

## Important difference: Antigravity schedules versus persistent sidecars

A session-local timer or schedule does **not** promise work across an app restart. Do not claim `/schedule` is available in this exact session if its UI says otherwise. Persistent sidecars use their own manifest and lifecycle and require a separate configuration, security review and authorization. **Do not create or activate sidecars as an implied extension of a prompt.**

Legacy Antigravity IDE Workflows were sunset on **19 October 2026** according to the current documentation. Prefer agent skills for reusable procedures rather than creating new legacy workflow files. Existing workflows can be migrated with `/migrate-workflows` after reviewing the specific effects.

## Current acceptance focus (snapshot only)

- [PR #835: claim safety and safe reclaim](https://github.com/happyhippovip/2026-courier/pull/835).
- [PR #836: provider DONE is not FINAL](https://github.com/happyhippovip/2026-courier/pull/836).
- [PR #837: A→B→C journal proof](https://github.com/happyhippovip/2026-courier/pull/837).

Check fresh branches, merges and CI at runtime rather than blindly replaying this list.

## Official references

- [Google Antigravity /goal](https://antigravity.google/docs/commands/goal)
- [Google Antigravity /schedule](https://antigravity.google/docs/commands/schedule)
- [Google Antigravity sidecars](https://antigravity.google/docs/sidecars)
- [Google Antigravity hooks](https://antigravity.google/docs/hooks)
- [Workflows to skills migration](https://antigravity.google/docs/migration/workflows-to-skills)

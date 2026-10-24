# Courier Symphony — Public Working Method
**Snapshot: 23 October 2026 · Happy Hippo VIP · Pre-release**

[GitHub project](https://github.com/happyhippovip/2026-courier) · [Happy Hippo VIP](https://github.com/happyhippovip) · [Public overview](./HAPPY_HIPPO_OVERVIEW_2026-10-23.md)

## What we're building

Courier Symphony is a local-first software project for getting computer tasks to a **verifiable finish**, rather than accepting an AI agent's claim that a task is done. It combines task orchestration, a durable event journal, bounded workers, verification, recovery and a desktop hub. The primary V1 direction is Windows-first, with cross-host testing on macOS and Linux.

**Status:** active development / pre-release. A passing synthetic test or CI run is not proof of production readiness or a real-provider end-to-end run.

## How we work: several specialized agents, one controlled integration path

Human direction is supported by separate development and verification roles. Current roles include Cursor, Claude, Google Antigravity, Codex and Grok-based reviewers where available. Their tool access, features and quotas differ; each agent must verify its actual environment.

| Area | Responsibility |
| --- | --- |
| L1 | Integration, CI, release gates and controlled merges |
| L2 | Controller, journal, admission and cost gates |
| L3 | Worker host, provider adapters and execution boundaries |
| L4 | Verification, receipts, synthetic proof and security tests |
| L5 | Desktop hub, UX and replay |
| L6 | Packaging, Windows installation, launcher and diagnostics |
| Independent reviewers | Cross-platform regression, red-team analysis and audit findings; read-only unless explicitly authorized |

A role assignment is **not** a repository write permission. Every conflicting edit needs a current authoritative owner and exclusive writer lease. We prefer independent read-only tests over simultaneous edits to the same code.

## Workkeys, not prompt storms

1. **Identify current truth.** Compare the latest branch, commit, CI state and previous checkpoint. Historical reports are evidence, not a license to replay work.
2. **Pick one real, new workkey.** It must be in the agent's approved scope, with a concrete acceptance condition.
3. **Prove the defect first.** Add a targeted negative test where practical and establish that it fails before the change.
4. **Fix in one owned area.** Keep other lanes untouched; pass a patch proposal or an audit to the owner instead.
5. **Verify.** Run targeted tests and appropriate broader CI. Record the exact commit and exit status.
6. **Checkpoint, then continue.** Deduplicate finished workkeys. Save concise evidence, blockers and the next authorized action.
7. **Integrate with review.** L1 owns promotion to the integration branch; publication, spending and other privileged actions retain their human gates.

An agent waiting on CI or permissions should do genuinely independent authorized work or go quiet. Repeating the same prompt or launching duplicate loops is not progress.

## Automation with limits

Our operating design explores longer-running goals, scheduled or event-driven wake-ups, scoped subagents and checkpoint-based resume, where **supported and enabled by the individual tool**. These are capabilities to configure and test, **not a claim that every account, window or host is currently running unattended**.

- **Goal:** persist the *purpose* and authorized scope.
- **Queue/workkeys:** persist distinct tasks and their status.
- **Loop or schedule:** only resume if the clock, quota, permissions and a genuinely open workkey allow it.
- **Event subscriptions:** prefer meaningful new commits, CI outcomes or review findings over busy polling.
- **Subagents:** parallel independent read-only analysis; one writer per conflict domain.
- **Stop/recovery:** a bounded stop mechanism, no double dispatch and an honest quiet state when no authorized task exists.

A 24-hour mission is a **time boundary**, not a guarantee of 24 hours of uninterrupted compute. One continuation mechanism per session avoids duplicate wake-ups. Cloud and other metered services are not enabled without verified authorization.

## Engineering invariants

```text
REAL_TRADES=0
WALLET_SIGNING=NO
AUTONOMOUS_SPEND_LIMIT_EUR=0
UNKNOWN_COST=BLOCK
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
NO_UNAUTHORIZED_MERGE=YES
```

The meaning matters more than a flag's presence: a command called `local_shell` is not automatically free, a provider's `DONE` message is not a verified result, and an expired lease is not proof that previous execution safely stopped.

We distinguish:
- **TESTED / SYNTHETIC_VERIFIED:** reproduced in tests or a controlled fixture;
- **CI_PASS:** specified automated checks passed for an exact commit;
- **REAL_PROVIDER_VERIFIED:** only when the actual authorized provider chain was executed and proven;
- **UNKNOWN / BLOCKED:** not validated, missing permissions or an incomplete evidence chain.

Fail closed on uncertain costs, ownership, artifacts, receipts, replay safety or proof.

## Current areas of focus (snapshot, 23 October 2026)

- [#835 — Claim safety, process nonce and explicit reclaim](https://github.com/happyhippovip/2026-courier/pull/835)
- [#836 — A provider DONE signal must not finalize a workkey](https://github.com/happyhippovip/2026-courier/pull/836)
- [#837 — A→B→C requires journal evidence before FINAL](https://github.com/happyhippovip/2026-courier/pull/837)

PR status and evidence evolve. Check the links and current CI rather than treating this snapshot as live release certification.

## Transparency and privacy

This document describes the **public engineering approach**, not private handoff material. Personal information, finances, medical records, account identifiers, access tokens, passwords, private machine paths, private project memory and internal security details do **not** belong in a public project overview.

Public code does not imply an open-source license: see the repository's current license status before reusing it.

---
**Our question:** How can tools that help us today become systems that safely learn how to help us better tomorrow?

# 🐦 Courier Symphony — public agent handoff / real progress vs. idle queues

**Date:** 2026-10-10 · **Status:** PUBLIC, evidence-separated developer handoff.  
**Audience:** future ChatGPT chats, Google Antigravity, Cursor, Grokbot and Claude **only when they actually read this URL**. A GitHub document does not push messages into those providers.

> **Founder intent:** Finish the existing Windows V1 as fast as safely possible; preserve existing work, stop repeated quota-consuming no-op reports, route distinct scoped jobs to their rightful owners and make next-session continuation possible without reopening every app or losing uncommitted work.

## 1. What prompted this handoff

A user-supplied ~31-second 2026-10-10 screen recording shows Windows Google Antigravity reporting a `V600` / maximum-build verification summary, claimed green tests and, in another turn, `STATUS_NO_SAFE_DISTINCT_WORK` on unchanged branches while queue messages keep returning. The screenshot is **not** a new independently reproducible CI/test log; the spoken audio has **not** been reliably transcribed here, so **no verbatim speech quotation or inferred verbal authorization** is recorded.

**Problem:** Reposting the same V50/V65/V100/V600 instruction can re-run the same completed/blocker classification. Even an immediate no-op model run may use subscription quota. `AUTONOMOUS_SPEND_LIMIT_EUR=0` prevents new purchases; it does **not** mean existing inference quota was free.

**Product-management requirement:** The founder needs ONE canonical, easily discoverable handoff; a next session must resume verified existing work and identify a *different* runnable workkey, not start from scratch. The UI must distinguish `TEST_PASS`, `REMOTE_COMMIT_VERIFIED`, `INTEGRATED`, `WINDOWS_CLEAN_MACHINE_ACCEPTED` and `24_7_AUTOMATION_VERIFIED`.

## 2. GitHub facts directly rechecked on 2026-10-10

- Repo: `happyhippovip/2026-courier`, public; default branch `main` is **not** the integration target `integration/v1`.
- `integration/v1` current verified SHA: `68de315616b70adcc24cdcd77577dc457e0d0da6` (historical snapshot; recheck when acting).
- [PR #410](https://github.com/happyhippovip/2026-courier/pull/410): OPEN and **not merged** at verification time; L1/founder integration gate, not a task to poll every iteration.
- [PR #349](https://github.com/happyhippovip/2026-courier/pull/349): OPEN, conflicting at verification; [PR #361](https://github.com/happyhippovip/2026-courier/pull/361): OPEN draft/continuity dependencies.
- The existing [PR #349 compatibility branch](https://github.com/happyhippovip/2026-courier/tree/lane/L2-pr349-compat-prep) **is truly remote**, HEAD `1d31022d744849824664495c24d1a2deb2909ff8`. It contains PR-349 preparation and canonical coordination-module imports. Independent GitHub proof establishes commits/files, **not** all runtime test claims.
- The existing [continuity-demo-preparation branch](https://github.com/happyhippovip/2026-courier/tree/lane/L2-continuity-demo-prep) is remote at `b3e7b9b21f9d8a45b8a5abf9520d2b333e781f9a`. Its test/review/merge status still requires exact evidence.

## 3. Distinguish remote truth from reports

**Reported from Windows Antigravity logs, not independently rerun here:**
- Prep-branch targeted tests: `test_ledger_tick.py` 29 PASS, `test_ledger_bridge_restart_matrix.py` 6 PASS, `test_golden_goal_ab_autonomous.py` 1 PASS.
- A subsequent V600 screenshot claims broader green tests, including packaging-related checks and a `V600_MAXIMUM_BUILD_CHECKPOINT.json`. Do not turn that screenshot into an overall Windows-V1 PASS, an already-integrated build or reliable 24/7 uptime.
- Worker protected uncommitted L1 workspace data and reported a local SHA-256 backup of changed/untracked individual files. Local snapshots are **not automatically remotely recoverable**; nested worktrees, original directory paths, stashes and unrelated project sources must be separately preserved and verified.
- Other app reports sometimes say `WINDOWS_LOCAL_ACCESS=UNKNOWN`; that is compatible with *another* local Windows agent having verified a checkout. Evidence has provenance per session/host; never replace local proof with a cloud chat's uncertainty or vice versa.

## 4. Mandatory work ownership and recovery rules

Read the live `AGENTS.md`, `docs/V1_RULE_0.md`, `docs/V1_ORCHESTRATION_PLAYBOOK.md`, `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`, `docs/NEXT_CHAT_HANDOFF.md`, and latest [Issue #54](https://github.com/happyhippovip/2026-courier/issues/54). Read the **latest** `integration/v1` head before making changes.

Locked V1 sequence: **ACTIVE LEDGER → RELIABLE AUTOMATION → GOLDEN PATH → DESKTOP HUB → WINDOWS EXE → CLEAN-MACHINE ACCEPTANCE → REAL ADAPTERS → DESKTOP ROBOT OVERLAY**.

Only existing **L1–L6** writer lanes. `SINGLE_WRITER=YES`, `HEAVY_JOB_LIMIT=1`, verified owner scope/claim, no writer collisions across Windows/Mac and no automatic merge to `integration/v1`. Historical ownership labels are **not** proof of an active process; a report that 'no other worker is running' is **not** proof that its uncommitted work is released.

Protect existing branches, stashes, nested worktrees and uncommitted files. No blanket `git clean`, hard resets, stash pops, unsafe cherry-picks, ACL bypass, extra scheduler, recursive agent swarm, account rotation for quotas, secrets in public repo, or purchases. Any exception requires separately verified authorization and scope.

## 5. A repeatable queue is not a queue of new tasks

**Never launch 65/100/600 identical queue turns merely because 1 build passed.** Each queued call has independent quota cost and may replay the same `NO_SAFE_DISTINCT_WORK` report.

Safe staged sequence:
1. One **real** existing independently runnable workkey, with stable fingerprint, verified ownership and bounded capacity.
2. One actual implementation/test cycle; verify necessary diff and exact local+remote state.
3. One second **different** workkey proves the shared progress/claim mechanism survives another turn, without repeating the first.
4. Only after distinct serial tasks AND an actually working, cost-controlled provider-native continuation are demonstrated, schedule further bounded units. If no work, `WAIT_FOR_OWNER`/idle means **pause queue**, not another inference request.
5. Native long-running automations are not established merely by keeping chat/IDE open. Verify trigger, authorized repository, running host, usage limits and recovery after restart. No claim of 24/7 without actual evidence.

Canonical fingerprint per unit: `WORKKEY | OWNER_LANE | FILE_SCOPE | BASE_HEAD | PRECONDITIONS | RESULT_RECEIPT`. Must persist in existing Courier ledger/authorized checkpoint. A local lock alone is insufficient across hosts.

## 6. Next **distinct** owner actions

- **L1 / integration owner:** assess #410 against current trunk, reviews/tests and the protected uncommitted L1 work. A human/founder gate is still required. Do not poll it in many model turns or assume merge approval from this document.
- **L2/L3 / authorized worker:** preserve `lane/L2-pr349-compat-prep`; check continuity-demo actual test status; reconcile `courier_worker/service.py` overlap **only** after its uncommitted owner work is safely reconciled/released; then safely complete #349 integration and missing targeted tests. Avoid reimporting canonical modules already committed.
- **L4/L5/L6:** take only truly free, preexisting scopes in the earliest eligible product stage, with targeted tests. Do not invent new build work to keep a queue busy.
- **Windows/Mac recovery:** separately verify real host paths, provenance, missing/offline backups and retained sessions. Public git commit ≠ copy of all local/USB/chat history.
- **Cursor/Grokbot/Claude:** read this handoff; self-identify real repo/host permissions. Cooperate through actual authorized shared state; do not pretend to receive each other's private conversation or direct messages. When access unavailable, return `SOURCE_REQUIRED`, not `DONE`.

## 7. Required answer for all agents / next chats

Return **only evidenced changes**:

```text
HOST_AND_ACCESS:
CURRENT_INTEGRATION_SHA:
CURRENT_WORKKEY:
EXCLUSIVE_OWNER_PROOF:
ACTUAL_CHANGE_OR_NEW_FINDING:
TEST_COMMAND_AND_RESULT:
LOCAL_COMMIT:
REMOTE_COMMIT_VERIFIED:
INTEGRATED_TO_V1: YES|NO|UNPROVEN
WINDOWS_ACCEPTANCE: PASS|FAIL|UNPROVEN
REMAINING_REAL_BLOCKER:
NEXT_DIFFERENT_RUNNABLE_WORKKEY:
QUEUE_ACTION: CONTINUE_BOUNDED|PAUSE
COST_OR_QUOTA_EVIDENCE:
```

If no free task: a **single short stop** and explicitly **PAUSE** repeated queue entries. Do not celebrate tests as a finished Windows product, invent 0 usage, or demand the user repeat previously established project history.

## 8. Privacy and source limits

This public handoff intentionally contains **no uploaded screen recording, no audio recording, no raw private export, no full local user folder paths, no tokens or account credentials**. Private detailed cross-app incident context is stored separately in the authorized private `2026-project-memory` repository. Do not copy it into public content without a new content-by-content review.

**This document is a public handoff, not proof any external app has read it, or an instruction to autonomously spend resources.**

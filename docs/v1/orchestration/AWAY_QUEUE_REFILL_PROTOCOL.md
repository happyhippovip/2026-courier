# Courier Symphony — Away / Queue Refill Protocol

Status: **AUTHORITATIVE DEVELOPMENT ORCHESTRATION RULE**

Purpose: keep one-hour / shower / sleep absences productive without forcing Dennis to sit at the keyboard and without recreating prompt storms, duplicate work, or Mac resource incidents.

This protocol applies to:
- Muse on the MacBook;
- Google Antigravity on the MacBook;
- Claude/Opus writer relay where applicable.

Read with:
- `docs/V1_ORCHESTRATION_PLAYBOOK.md`
- `docs/v1/orchestration/REPEATABLE_QUEUE_TOKENS.md`
- `docs/v1/orchestration/MUSE_MAC_LOW_FD_SINGLE_AGENT.md`
- `.agents/skills/courier-night-loop/SKILL.md`
- `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`

## 1. General rule

The owner should be able to leave for roughly an hour or sleep without hand-feeding every short turn.

The durable pattern is:

**one owner session -> durable queue state -> self-refill from current evidence -> dedupe -> bounded useful unit -> repeat**

Never substitute:
- dozens of windows;
- repeated identical analysis;
- duplicate writers;
- child-agent explosions;
- artificial work created only to stay busy.

A queue token may be repeated many times only if it is **stateful and idempotent**:
- it reads the durable queue state first;
- it claims the first unfinished unit;
- it never repeats an accounted fingerprint;
- it refills only from CURRENT repo evidence when the backlog is empty.

## 2. Muse MacBook — primary unattended mode

Preferred:
```
/loop 5m /courier-night-loop
```

This is the default one-window unattended mode after the skill exists in the checked-out branch.

If the loop is unavailable or a one-off refill is needed, use the emergency refill prompts below.

### Muse emergency refill A — critical path

```text
COURIER MUSE — EMERGENCY REFILL A / CRITICAL PATH

ONE AGENT ONLY.
NO workflow.
NO /goal.
NO child agents.
NO subagents.
NO background jobs.
NO new terminal.
NO product-source edits.
NO branch/commit/merge.
NO broad suites.

Read /tmp/courier-v1/night-loop/STATE.md if present.
Verify CURRENT integration/v1 cheaply.

If RESOURCE_PAUSE=YES, stop without probing.

If backlog contains unfinished evidence-backed work:
continue from the first unfinished highest-priority item.

If backlog is empty:
create up to 12 NEW non-duplicate units from CURRENT evidence, prioritizing:
1. L2 Controller/API blockers
2. L3 worker/process-safety blockers
3. L4 verifier/synthetic blockers
4. Golden happy/failure/restart/replay gaps
5. exact missing targeted tests

Fingerprint each unit by:
HEAD|LANE|FILE_OR_FUNCTION|RISK_OR_TEST_QUESTION

Never add a fingerprint already completed for the same head.

Then complete the highest-priority unit thoroughly this turn.
Persist evidence, smallest targeted test, owner lane, stage blocked, follow-up, next unit.

If EMFILE / Too many open files / os error 24 / spawn pressure occurs:
set RESOURCE_PAUSE=YES if possible;
do not retry;
stop.

Final:
COURIER_REFILL_A_COMPLETE
```

### Muse emergency refill B — product / acceptance

```text
COURIER MUSE — EMERGENCY REFILL B / PRODUCT ACCEPTANCE

ONE AGENT ONLY.
NO workflows/children/subagents/background jobs.
READ-ONLY.

Read existing night-loop state and CURRENT repo truth.

Add only NEW non-duplicate evidence-backed units for:
- Golden Path acceptance
- Desktop Hub journal/SSE/replay truth
- customer error/Human Desk behavior
- Windows entrypoint/path/shutdown contract
- diagnostics/redaction
- clean-machine install/reopen/uninstall
- idle power / responsiveness regressions

Do not add speculative features.
Do not duplicate completed fingerprints.

Complete the first highest-priority new unit thoroughly and persist it.

If no honest new unit exists:
record IDLE_PRODUCT_ACCEPTANCE and stop.

On EMFILE/resource pressure:
RESOURCE_PAUSE and stop without retry.

Final:
COURIER_REFILL_B_COMPLETE
```

### Muse emergency refill C — harvest / contradiction

```text
COURIER MUSE — EMERGENCY REFILL C / HARVEST

ONE AGENT ONLY.
READ-ONLY.
NO workflow/children/subagents.

Read:
- current night-loop state
- latest CURRENT integration/v1
- latest known lane/PR evidence available to this session
- existing local Courier review checkpoints

Do one deep reconciliation pass:

- deduplicate old findings;
- mark superseded findings;
- challenge false positives;
- detect contradictions between current code/tests/docs;
- map every real issue to exactly one L1-L6 owner;
- produce the smallest targeted verification for each real blocker;
- do not resurrect historical issues already fixed.

Persist a compact harvest result into the night-loop state.

If nothing new is proven:
record HARVEST_NO_NEW_EVIDENCE and stop.

Final:
COURIER_REFILL_C_COMPLETE
```

These three are emergency refills, not a reason to stack hundreds of Muse messages.

## 3. Google Antigravity MacBook — repeatable large queue token

Antigravity may use a deeper manual queue when the session executes queued messages serially.

Use one session and one durable artifact:

`ANTIGRAVITY_COURIER_REFILL_LEDGER`

### Bootstrap once

```text
COURIER ANTIGRAVITY — BOOTSTRAP SELF-REFILLING REVIEW LEDGER

READ-ONLY.

Create or continue one artifact:
ANTIGRAVITY_COURIER_REFILL_LEDGER

Verify CURRENT integration/v1.

Ledger fields:
EPOCH_HEAD
COMPLETED_FINGERPRINTS
WAITING
BACKLOG
LAST_UNIT
NEXT_UNIT
GENERATION

Fingerprint:
HEAD|LANE|FILE_OR_FUNCTION|QUESTION_OR_RISK

Build an initial backlog of up to 32 evidence-backed units from:
- L2 controller/API/restart/concurrency/corruption/SSE
- L3 process/outbox/resource/power
- L4 verifier/evidence/synthetic
- Golden lifecycle/failures/replay
- L5 Desktop Hub truth
- L6 Windows EXE/diagnostics/clean-machine
- only concrete future-rework prevention

Do not do all units now.
Initialize the ledger, identify NEXT_UNIT, and stop.

No subagents.
No product-source edits.
No branches/commits/merges.
```

### Repeatable token — safe to enqueue many times in the same serial session

```text
COURIER ANTIGRAVITY — NEXT SELF-REFILLING UNIT

Continue ANTIGRAVITY_COURIER_REFILL_LEDGER.

Do exactly ONE NEW useful unit.

1. Read the ledger first.
2. Verify CURRENT integration/v1 cheaply.
3. If HEAD changed:
   - begin a new GENERATION for the new head;
   - inspect the delta;
   - refill BACKLOG with up to 32 new evidence-backed units.
4. If BACKLOG is empty on the same head:
   - derive up to 16 NEW units from current unresolved evidence;
   - prioritize correctness, failing/weak tests, restart/concurrency/process safety, Golden blockers, Desktop/EXE acceptance;
   - use future work only when it protects a concrete current compatibility boundary.
5. Select the highest-priority unit whose fingerprint is not completed/waiting.
6. Complete it thoroughly.
7. Persist:
   STATUS
   EVIDENCE
   FILES_FUNCTIONS
   FAILURE_CONSEQUENCE
   SMALLEST_TEST
   OWNER_LANE
   BLOCKS_STAGE
   FOLLOWUP
   NEXT_UNIT
8. Add its fingerprint to completed/waiting.
9. Stop.

Never repeat a completed fingerprint for the same head.
Never invent busywork.
No subagents.
No product-source edits.
No branches/commits/merges.
No broad suites.

If no honest work exists:
record IDLE_AT_HEAD and stop this token.

Final:
ANTIGRAVITY_UNIT_COMPLETE
or
ANTIGRAVITY_IDLE_AT_HEAD
```

This token may be queued 65x or 100x **only in one serial Antigravity session**.
If the provider starts queued items concurrently, do not use mass enqueue; use a single recurring/agent skill instead.

## 4. One-hour owner-away routine

Before leaving:

### Muse
Preferred:
`/loop 5m /courier-night-loop`

If not available:
- queue at most A, B, C once each;
- do not build a giant Muse message backlog.

### Antigravity
- bootstrap once if ledger does not exist;
- enqueue the repeatable NEXT SELF-REFILLING UNIT token as deeply as the UI supports serially (e.g. 65 or 100);
- one session only.

### Claude/Opus
- sequential writer relay prompts only on the official writer branch;
- no overlapping writer windows.

## 5. Return / harvest

When Dennis returns:
- do not assume all queued tokens did useful work;
- inspect completed fingerprints/results;
- deduplicate;
- discard idle/no-new-evidence turns;
- promote only evidence-backed actionable findings to L1-L6;
- update current orchestration state;
- re-arm the loop/token only if there is still useful unresolved work.

## 6. Why this is durable

The queue is not a fixed list that eventually empties forever.

It can refill when:
- the integration head changes;
- a writer branch lands;
- a test/gate changes;
- current evidence exposes a new unresolved dependency.

It still refuses to invent work when nothing new exists.

That distinction is mandatory:
**self-refilling does not mean fake-infinite work.**

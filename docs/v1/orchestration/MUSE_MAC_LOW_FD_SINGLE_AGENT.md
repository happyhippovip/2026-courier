# Muse Mac Low-FD Single-Agent Queue

Status: **PREFERRED MAC MODE WHILE EMFILE / HEAT EVIDENCE EXISTS**

Use this instead of a child-workflow fanout when the Mac has shown:
- `Too many open files`
- `EMFILE`
- `os error 24`
- child-session writer lease failures
- excessive heat/fan activity

This mode intentionally uses **one Muse session, one agent, zero child agents, zero workflows, zero subagents**.

It trades parallelism for reliability and lower host pressure.

## Why this exists

A live 144-cell Muse factory was generated into 12 family workers and failed under file-descriptor pressure before producing trustworthy evidence. The failure was orchestration infrastructure, not a product-code verdict.

Therefore, on an affected Mac:
- do not retry the 144-child factory;
- do not use child fanout merely because the logical queue is large;
- process many logical packets sequentially in one retained session.

## Launch

Use a fresh retained Muse session.

Recommended:
- model: `muse-spark-1.3-contributor`
- reasoning: xhigh
- read-only
- no YOLO required
- no `/goal`
- no workflow
- no subagents

Paste the following **once** as a normal prompt.

```text
COURIER SYMPHONY — MAC LOW-FD SINGLE-AGENT DEEP QUEUE

IMPORTANT:
DO NOT USE A WORKFLOW.
DO NOT USE /goal.
DO NOT SPAWN CHILD AGENTS.
DO NOT USE SUBAGENTS.
DO NOT START BACKGROUND JOBS.
DO NOT RUN /loop.
DO NOT OPEN NEW TERMINALS.

REPO:
happyhippovip/2026-courier

VERIFY CURRENT integration/v1 FIRST.

FIRST READ:
- AGENTS.md if present
- docs/V1_RULE_0.md
- docs/V1_PRODUCT_QUALITY_BAR.md
- docs/V1_ORCHESTRATION_PLAYBOOK.md if present
- docs/V1_WINDOW_CUSTODY_PROTOCOL.md if present
- docs/NEXT_CHAT_HANDOFF.md
- newest relevant GitHub Issue #54 rules
- docs/v1/INTEGRATION_LOG.md
- tests/golden/README.md
- tests/golden/test_golden_happy.py
- tests/golden/test_golden_failures.py

RULE 0:
FINISH THE PRODUCT.

ROLE:
One read-only senior reviewer working sequentially.

HOST SAFETY:
This Mac has prior EMFILE / os error 24 evidence.

If any new shell/file operation returns:
Too many open files
EMFILE
os error 24
resource-pressure/spawn failure

THEN:
- stop all new tool spawning
- write RESOURCE_PAUSE in the checkpoint if possible
- do not retry the failed command
- do not run diagnostics loops
- do not start helpers
- return the current checkpoint state

NO:
- product source edits
- branch/worktree creation
- commits/merges
- broad test suites
- provider calls
- architecture redesign
- repeated whole-repo scans
- artificial waiting

CHECKPOINT:
Maintain one compact checkpoint only:
 /tmp/courier-v1/mac-low-fd/CHECKPOINT.md

After each packet append:
PACKET:
STATUS: DONE|BLOCKED_WITH_EVIDENCE|RESOURCE_PAUSE
EVIDENCE:
FILES/FUNCTIONS:
REAL_GAP:
SMALLEST_TEST:
OWNER_LANE:
NEXT_PACKET:

Do not re-read completed packet scope unless later evidence contradicts it.

PROCESS THESE 36 PACKETS SEQUENTIALLY:

01 L2 controller startup/CLI
02 L2 token/auth
03 L2 task-create validation
04 L2 exactly-one claim
05 L2 start fencing
06 L2 heartbeat/lease semantics
07 L2 restart_grace
08 L2 duplicate result
09 L2 stale/late result
10 L2 cancel/shutdown
11 L2 SSE ordering/reconnect
12 L2 corruption/degraded-readonly

13 L3 worker API dependency map
14 L3 process spawn ownership
15 L3 timeout/cancel cleanup
16 L3 child/grandchild safety
17 L3 result outbox
18 L3 worker restart
19 L3 heartbeat/lease margin
20 L3 stdout/stderr bounds
21 L3 logs/descriptor risks
22 L3 resource-probe fail-open
23 L3 idle/power/wakeup map
24 L3 targeted failure-test matrix

25 L4 result identity binding
26 L4 artifact/path/sha256 safety
27 L4 malformed/empty evidence
28 L4 synthetic adapter minimum
29 Golden happy-path gap map
30 Golden failure-injection gap map

31 L5 journal/SSE/replay UI boundary
32 L5 customer error/Human Desk states
33 L6 Windows entrypoint/path requirements
34 L6 diagnostics/redaction/clean shutdown
35 future adapter/mobile/overlay contracts worth preserving NOW
36 final deduplicated Opus/L1 handoff

For every packet classify:
PROVEN
MISSING
CONTRADICTED
LEGACY_ONLY
WAIT_FOR_L2
DEFER_AFTER_EXE

Do not stop merely because one packet found no issue.
Do not stop merely because one bug was found.

FINAL OUTPUT in checkpoint:

CURRENT_HEAD:
PACKETS_DONE:
PACKETS_BLOCKED:
REAL_L2_BLOCKERS:
REAL_L3_BLOCKERS:
REAL_L4_BLOCKERS:
GOLDEN_BLOCKERS:
L5_PREP:
L6_PREP:
FALSE_ALARMS_REMOVED:
POWER_RESOURCE_RISKS:
EXACT_OPUS_TASKS:
EXACT_L1_GATES:
SAFE_NEXT_WRITER_ACTIVATION:

FINAL MARKER only after packets 01-36 are accounted for:
MAC_LOW_FD_QUEUE_COMPLETE
```

## Completion / reuse

If the session returns before 36/36:
- do not paste the full prompt again;
- paste only:

```text
Resume the MAC LOW-FD queue from the FIRST checkpoint packet not marked
DONE or BLOCKED_WITH_EVIDENCE.

Do not repeat completed packets.
Do not spawn children/workflows/subagents.
If RESOURCE_PAUSE is present, stop instead of retrying.
```

## Cleanup

When complete, run the window custody check before `/clear` or close.

Do not keep the completed Muse process alive merely to preserve text that has already been checkpointed/durably harvested.

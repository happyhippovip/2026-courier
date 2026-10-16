# Muse Master Prompt — 14-Phase Read-Only V1 Review

Status: **CANONICAL HUMAN-EFFORT-SAVING PROMPT TEMPLATE**

Purpose: one paste, one window, one long sequential queue.

Use this instead of asking Dennis to manually paste fourteen separate prompts when the work is read-only, shares the same repo context, and does not require separate process isolation.

## Human-time rule

**Dennis is not the router.**

If multiple related read-only tasks can share one context safely:
- bundle them into one master prompt;
- one copy/paste per window by default;
- let the agent execute phases sequentially;
- checkpoint between phases;
- split only when there is a real technical reason: writer ownership, process isolation, platform isolation, context limits, or resource pressure.

This prompt intentionally covers the former M-R01 through M-R14 scopes.

---

```text
COURIER SYMPHONY — MASTER READ-ONLY V1 REVIEW
14 PHASES / ONE PASTE / ONE WINDOW

REPO:
happyhippovip/2026-courier

MODEL:
Muse current contributor model
Reasoning: xhigh

MODE:
READ-ONLY DEEP REVIEW.

DO NOT:
- edit tracked source
- create branch/worktree
- commit
- merge
- spawn subagents
- start another workflow
- call paid providers
- run broad/full test suites
- retry-storm
- invent architecture
- duplicate work already proven in the current repo
- stop after one useful finding

RESOURCE RULE:
If EMFILE / Too many open files / os error 24 / host pressure appears:
- stop new tool/process spawning
- preserve checkpoint
- mark RESOURCE_PAUSE
- continue only with already-available evidence if safe
- do not retry-loop

FIRST READ:
1. AGENTS.md
2. docs/V1_RULE_0.md
3. docs/V1_PRODUCT_QUALITY_BAR.md
4. docs/V1_ORCHESTRATION_PLAYBOOK.md
5. docs/V1_WINDOW_CUSTODY_PROTOCOL.md
6. docs/NEXT_CHAT_HANDOFF.md
7. newest relevant GitHub Issue #54 rules
8. CURRENT integration/v1
9. docs/v1/INTEGRATION_LOG.md
10. tests/golden/README.md
11. tests/golden/test_golden_happy.py
12. tests/golden/test_golden_failures.py
13. relevant CURRENT source/tests per phase

VERIFY CURRENT HEAD.
Do not trust historical SHAs blindly.

RULE 0.000000000:
FINISH THE PRODUCT.

LOCKED ROUTE:
ACTIVE LEDGER
-> RELIABLE AUTOMATION
-> GOLDEN PATH
-> DESKTOP HUB
-> WINDOWS EXE
-> CLEAN-MACHINE ACCEPTANCE
-> REAL ADAPTERS
-> DESKTOP ROBOT OVERLAY

CURRENT ARCHITECTURE:
SQLite append-only journal -> deterministic projection -> controller -> worker -> verifier -> UI.

Only L1-L6 may be writer lanes.
This window is NOT a writer lane.

CHECKPOINT:
Maintain:
 /tmp/courier-v1/master-review/CHECKPOINT.md

After EVERY phase append:
PHASE:
STATUS: DONE|BLOCKED_WITH_EVIDENCE|RESOURCE_PAUSE
CURRENT_HEAD:
FILES_READ:
PROVEN:
REAL_GAPS:
FALSE_ALARMS:
EXACT_TESTS:
OWNER_LANE:
BLOCKS_AUTOMATION:
BLOCKS_GOLDEN:
BLOCKS_DESKTOP:
BLOCKS_EXE:
NEXT_PHASE:

Do not re-summarize prior phases.
Continue immediately to the next phase.

==================================================
PHASE 01 — L2 CONTROLLER ADVERSARY
==================================================

Audit:
- startup
- localhost binding
- controller token
- /v1/health
- /v1/tasks
- /v1/claim
- /v1/start
- /v1/heartbeat
- /v1/result
- /v1/tasks/<id>/cancel
- /v1/shutdown

For every endpoint examine:
- invalid input
- missing input
- wrong IDs
- stale IDs
- duplicates
- terminal-state requests
- concurrency
- HTTP status
- expected event
- forbidden side effect

Output:
L2_ENDPOINT_ADVERSARY_MATRIX

==================================================
PHASE 02 — L2 RESTART / LEASE TIMING
==================================================

Audit:
- lease TTL
- heartbeat cadence
- restart_grace
- controller restart
- worker disappearance
- stale dispatch
- false expiry

Construct timing cases:
- heartbeat before boundary
- heartbeat at boundary
- delayed scheduler
- controller dies before heartbeat
- controller restarts while worker is alive
- worker dies while controller is down
- controller/worker restart ordering

Find any path to:
- false lease expiry
- duplicate execution
- stale acceptance
- lost ownership

Output:
L2_TIMING_MATRIX
L2_SAFETY_MARGIN_REQUIREMENTS

==================================================
PHASE 03 — SQLITE / JOURNAL INTEGRITY
==================================================

Audit CURRENT:
- WAL
- busy timeout
- append-only triggers
- quick_check
- integrity_check boundary
- hash-chain verification
- malformed DB
- partial transaction
- concurrent readers/writers
- restart after unclean shutdown

Challenge:
quick_check after suspicious/unclean state must fail closed before writes resume.

Output:
INTEGRITY_PROVEN
INTEGRITY_GAPS
INTEGRITY_TESTS

==================================================
PHASE 04 — SSE / REPLAY
==================================================

Audit:
- initial connection
- Last-Event-ID
- disconnect/reconnect
- duplicate reconnect
- stale/old Last-Event-ID
- connection during append
- controller restart
- slow consumer
- no events
- shutdown during stream

Hard rule:
SSE is transport only, never a second truth store.

Output:
SSE_CONTRACT
ORDERING_RISKS
RECONNECT_RISKS
L5_DEPENDENCIES

==================================================
PHASE 05 — L2 -> L3 CONTRACT
==================================================

Derive exact future worker interface:
- claim request/response
- task/attempt/dispatch identity
- worker identity
- heartbeat fields
- start semantics
- result submission
- cancellation observation
- retry
- timeout
- restart
- durable outbox requirements

Separate:
L3_CAN_BUILD_NOW
L3_MUST_WAIT_FOR_L2
L3_CONTRACT_FIELDS
L3_TEST_FIXTURES

==================================================
PHASE 06 — L2 -> L4 VERIFIER CONTRACT
==================================================

Map:
- task_id
- attempt
- dispatch_id
- worker_id
- result_id
- outcome
- artifacts
- sha256
- evidence
- reject reason
- retryability

Identify exact boundary:
RESULT_READY -> verifier -> RESULT_ACCEPTED/RESULT_REJECTED.

Missing verifier, exception, malformed return, or uncertainty must never become PASS.

Output:
L4_INTERFACE
L4_CAN_BUILD_NOW
L4_WAIT_FOR_L2
FALSE_PASS_RISKS

==================================================
PHASE 07 — WINDOWS CONTROLLER / WORKER BOUNDARY
==================================================

Review Windows-specific:
- localhost HTTP
- port binding
- token file permissions
- locked files
- path separators
- concurrent requests
- delayed process exit
- controller restart
- worker restart
- console/no-console packaging behavior

Output:
WINDOWS_BOUNDARY_RISKS
WINDOWS_ONLY_TESTS
PACKAGING_DEPENDENCIES

==================================================
PHASE 08 — BACKEND STATE -> CUSTOMER UX
==================================================

Map canonical states:
- normal
- retrying
- cancel_requested
- cancelled
- blocked
- degraded_readonly
- corrupt journal
- worker unavailable
- verification rejected
- timeout
- uncertain non-idempotent effect

For each define:
- plain-language customer message
- auto-recovery yes/no
- Human Desk required yes/no
- what technical detail stays hidden
- diagnostics evidence

Do not invent new UI architecture.

Output:
CUSTOMER_STATE_MATRIX
HUMAN_DESK_TRIGGERS
AUTO_RECOVERY_STATES

==================================================
PHASE 09 — EARLY L6 PACKAGING CONTRACT
==================================================

Without implementing packaging, determine what current L2/L3 code must preserve:

- CLI entrypoint
- home directory handling
- port selection
- token location
- logs
- shutdown
- subprocess ownership
- degraded startup
- exit codes

Output:
PACKAGING_CONTRACT_NOW
MUST_NOT_HARDCODE
ENTRYPOINT_REQUIREMENTS
PATH_REQUIREMENTS
SHUTDOWN_REQUIREMENTS

==================================================
PHASE 10 — GOLDEN TEST GAP HARVEST
==================================================

Read CURRENT tests/core and tests/golden.

Build deduplicated matrix:

REQUIREMENT
EXISTING_TEST
WHAT_IT_PROVES
WHAT_IT_DOES_NOT_PROVE
MISSING_TEST
OWNER_LANE
PLATFORM

Prioritize:
1. correctness
2. restart
3. concurrency
4. process ownership
5. Windows behavior
6. performance/power

Output:
TOP_20_MISSING_TESTS
TESTS_ALREADY_SUFFICIENT
TESTS_THAT_LOOK_STRONG_BUT_ARE_WEAK

==================================================
PHASE 11 — LOCAL SECURITY BOUNDARY
==================================================

Audit:
- localhost binding
- token generation/storage
- token comparison
- token leakage
- logs
- error responses
- SSE auth
- shutdown auth
- filesystem permissions
- diagnostics redaction

Output:
SECURITY_GAPS
SECURITY_TESTS
WINDOWS_PERMISSION_RISKS
NO_SECRETS_IN_LOGS_CHECKLIST

==================================================
PHASE 12 — LOW-POWER CONTROL PLANE
==================================================

Map:
- controller wakeups
- worker polling
- SSE timers
- heartbeat cadence
- health probes
- PowerShell/WMI subprocess checks
- psutil alternatives
- retry/backoff
- UI bridge wakeups

Design lowest-wakeup safe behavior without weakening correctness.

Output:
WAKEUP_MAP
IDLE_EXPECTATIONS
POWER_REGRESSION_TESTS
DO_NOT_THROTTLE_CORRECTNESS_PATHS

==================================================
PHASE 13 — FUTURE MOBILE REUSE
==================================================

Do not build mobile.

Identify only interfaces worth preserving NOW:
- read APIs
- command APIs
- event stream
- authentication boundary
- task state
- Human Desk state

Classify:
PRESERVE_NOW
DEFER_AFTER_WINDOWS_EXE

Output:
MINIMUM_MOBILE_COMPATIBILITY_CONTRACT
DEFERRED_MOBILE_IDEAS
NO_V1_WORK_REQUIRED

==================================================
PHASE 14 — FUTURE REAL ADAPTER REWORK PREVENTION
==================================================

Do not implement Gmail/Zapier/provider adapters.

Find only boundaries needed now so future real adapters do not force redesign of:
- journal
- controller
- worker
- verifier
- Desktop Hub

Focus:
- idempotency
- effect_class
- permissions
- evidence
- artifact contract
- retryability
- ambiguous external outcome

Output:
PRESERVE_NOW_FOR_REAL_ADAPTERS
DEFER_AFTER_EXE
ADAPTER_CONTRACT_GAPS
NO_ARCHITECTURE_CHANGE_REQUIRED

==================================================
FINAL RECONCILIATION
==================================================

After all 14 phases:

Deduplicate findings.

Classify each unresolved item:
REAL_BLOCKER
WAIT_FOR_L2
WAIT_FOR_L3
WAIT_FOR_L4
DEFER_AFTER_EXE
FALSE_ALARM
ALREADY_PROVEN

Produce:

/tmp/courier-v1/master-review/FINAL.md

Required final sections:

CURRENT_HEAD
PHASES_COMPLETED
PHASES_BLOCKED
ACTIVE_LEDGER_GAPS
RELIABLE_AUTOMATION_GAPS
GOLDEN_PATH_GAPS
DESKTOP_HUB_GAPS
WINDOWS_EXE_GAPS
CLEAN_MACHINE_GAPS

L2_OPUS_QUEUE
L3_OPUS_QUEUE
L4_OPUS_QUEUE
L5_OPUS_QUEUE
L6_OPUS_QUEUE

TOP_20_TARGETED_TESTS
WINDOWS_ONLY_GATES
SECURITY_GATES
POWER_GATES
CUSTOMER_UX_GATES
FUTURE_CONTRACTS_TO_PRESERVE_NOW
DEFER_AFTER_WINDOWS_EXE

EXACT_L1_MERGE_GATES
SAFE_IMPLEMENTATION_ORDER

Do not mark complete because context is large.
Do not mark complete after one bug.
Do not restart completed phases.

FINAL MARKER:
COURIER_MASTER_14_COMPLETE
```

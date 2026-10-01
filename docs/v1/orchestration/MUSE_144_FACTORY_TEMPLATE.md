# Muse 144-Task Overnight Factory Template

Status: **REUSABLE READ-ONLY FACTORY TEMPLATE**

Use this when Courier needs a large amount of overnight read-only engineering work without reopening the old uncontrolled prompt-swarm pattern.

## How to launch

1. Use a **fresh retained Muse session**.
2. Do **not** use `--no-session-log`.
3. In `/settings`, set Tools -> Workflows to `explicit` or `auto`.
4. Paste the factory prompt below as a **normal prompt**, not `/goal`.
5. Paste it **once**.
6. Monitor with bounded `/workflows` checks and use `/recap` after stepping away.
7. Do not `/clear` or close the workflow owner until custody is proven safe.

If the session reports Goal Store provenance/backend errors, do not retry `/goal`; this factory does not require Goal Store.

Resource rule: at most three investigator children active at once. Any EMFILE / os error 24 / host-pressure signal pauses new child launches. Do not repeatedly probe local files or run status loops under pressure; preserve the retained workflow and wait for terminal delivery when possible.

---

```text
COURIER SYMPHONY — 144 TASK OVERNIGHT FACTORY

USE A MUSE WORKFLOW.

IMPORTANT:
DO NOT USE /goal.
DO NOT REQUIRE THE GOAL STORE.

REPO:
happyhippovip/2026-courier

VERIFY CURRENT integration/v1 FIRST.

FIRST READ:
- AGENTS.md
- docs/V1_RULE_0.md
- docs/V1_PRODUCT_QUALITY_BAR.md
- docs/V1_ORCHESTRATION_PLAYBOOK.md
- docs/V1_WINDOW_CUSTODY_PROTOCOL.md
- docs/NEXT_CHAT_HANDOFF.md
- newest relevant GitHub Issue #54 rules
- docs/v1/INTEGRATION_LOG.md
- tests/golden/README.md
- tests/golden/test_golden_happy.py
- tests/golden/test_golden_failures.py
- relevant CURRENT source/tests for each packet

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

MODE:
READ-ONLY DEEP ENGINEERING FACTORY.

NO:
- tracked source edits
- branch creation
- commits
- merges
- paid provider actions
- architecture redesign
- historical swarm resurrection
- broad repeated test suites
- recursive child agents
- artificial work merely to consume quota

WORKFLOW SHAPE:

There are THREE BANKS.

Each BANK contains TWELVE WAVES.

Each WAVE contains:
- Investigator A
- Investigator B
- Investigator C
- one Verifier/Reconciler AFTER A/B/C finish

Therefore:
12 waves × 4 child tasks = 48 child tasks per bank.

BANK 1 = 48
BANK 2 = 48
BANK 3 = 48

TOTAL = EXACTLY 144 CHILD TASKS.

RESOURCE LIMIT:

At most THREE investigator child tasks may be active simultaneously.

For every wave:
1. launch A/B/C
2. WAIT until all three finish
3. launch exactly ONE verifier
4. persist verified synthesis
5. proceed to next wave

Never overlap waves.
Never recursively fan out from child tasks.

If EMFILE / Too many open files / os error 24 /
resource pressure / repeated shell failure appears:
- launch no new children
- preserve all completed results
- write RESOURCE_PAUSE
- do not retry-storm
- return a recoverable workflow state

==================================================
BANK 1 — RUNTIME / RELIABLE AUTOMATION
48 CHILD TASKS
==================================================

WAVE 01 — L2 API + AUTH
A: task-create/API validation
B: controller token/auth boundary
C: health/shutdown semantics
Verifier: reconcile against Golden contract

WAVE 02 — CLAIM / START
A: exactly-one claim semantics
B: attempt/dispatch identity
C: start fencing/idempotency
Verifier: search for duplicate-claim paths

WAVE 03 — HEARTBEAT / LEASE
A: heartbeat semantics
B: lease TTL safety margin
C: reclaim behavior
Verifier: prove live work cannot be falsely expired

WAVE 04 — CONTROLLER RESTART
A: restart during healthy worker execution
B: restart_grace
C: vanished-worker behavior
Verifier: search for duplicate-execution paths

WAVE 05 — RESULT INTAKE
A: normal result
B: duplicate result
C: stale/late result
Verifier: prove exactly-once acceptance

WAVE 06 — CORRUPTION / TRUTH
A: hash-chain failure
B: projection/rebuild equivalence
C: degraded-readonly behavior
Verifier: prove fail-closed truth

WAVE 07 — SSE / LIVE EVENTS
A: ordering
B: Last-Event-ID/reconnect
C: duplicate notifications
Verifier: prove no second event truth

WAVE 08 — PROCESS OWNERSHIP
A: Mac process groups
B: Windows process tree
C: Windows Job Object integration points
Verifier: exact owned-process containment

WAVE 09 — TIMEOUT / CANCEL / REAP
A: timeout
B: cancellation
C: parent-child-grandchild cleanup
Verifier: prove zero Courier-owned survivors

WAVE 10 — OUTBOX / CRASH
A: durable result outbox
B: crash during delivery
C: restart + redelivery
Verifier: prove no lost accepted result

WAVE 11 — RESOURCE / POWER
A: EMFILE/handle/descriptor risks
B: stdout/stderr/log growth
C: polling/wakeup/resource probes
Verifier: lowest-power safe design

WAVE 12 — RUNTIME FAILURE MATRIX
A: concurrency tests
B: crash/restart tests
C: Windows-specific failure tests
Verifier: final L2/L3 implementation dossier

Persist BANK 1 synthesis to:
/tmp/courier-v1/factory/BANK1_RUNTIME.md

==================================================
BANK 2 — GOLDEN / PRODUCT / WINDOWS EXE
48 CHILD TASKS
==================================================

WAVE 13 — VERIFIER IDENTITY
A: task/attempt identity
B: dispatch/worker identity
C: result identity
Verifier: false-PASS search

WAVE 14 — ARTIFACT SAFETY
A: path confinement
B: sha256/tampering
C: malformed/empty evidence
Verifier: evidence safety contract

WAVE 15 — SYNTHETIC ADAPTER
A: deterministic success
B: crash/hang/timeout
C: transient retry behavior
Verifier: minimum Golden implementation

WAVE 16 — GOLDEN HAPPY PATH
A: event lifecycle
B: artifact acceptance
C: shutdown/restart/replay
Verifier: exact acceptance gap map

WAVE 17 — GOLDEN FAILURE PATHS
A: worker/controller crash
B: timeout/cancel
C: duplicate/stale/non-idempotent cases
Verifier: coverage completeness

WAVE 18 — DESKTOP TRUTH
A: journal -> UI
B: SSE -> UI
C: projection/replay -> UI
Verifier: ensure no second orchestrator

WAVE 19 — REPLAY / ROBOTS
A: deterministic scene state
B: real lifecycle mapping
C: no fake activity
Verifier: same journal => same logical scene

WAVE 20 — ERROR UX
A: automatic recovery UX
B: Human Desk UX
C: diagnostics/details UX
Verifier: customer never needs developer knowledge

WAVE 21 — RESPONSIVENESS
A: UI-thread blocking
B: startup/navigation
C: timers/background work
Verifier: butter-smooth measurement plan

WAVE 22 — PACKAGING
A: PyInstaller onedir
B: Inno Setup/per-user install
C: LOCALAPPDATA/single instance
Verifier: packaging prerequisite map

WAVE 23 — DIAGNOSTICS / PRIVACY
A: bounded logs
B: secret redaction
C: local-first/private-data behavior
Verifier: clean diagnostics contract

WAVE 24 — CLEAN WINDOWS ACCEPTANCE
A: install/launch/Golden
B: close/reopen/replay
C: diagnostics/uninstall/no orphans
Verifier: full Windows 11 acceptance dossier

Persist BANK 2 synthesis to:
/tmp/courier-v1/factory/BANK2_PRODUCT.md

==================================================
BANK 3 — FUTURE-REWORK PREVENTION
48 CHILD TASKS
==================================================

IMPORTANT:
This bank does NOT add future features now.

Its purpose is only to identify small contracts we should preserve NOW
so later stages do not require expensive rewrites.

Anything that would delay the Windows V1 without protecting a concrete
compatibility boundary must be marked DEFER.

WAVE 25 — REAL ADAPTER CONTRACT
A: adapter input boundary
B: result/evidence boundary
C: idempotency/effect classification
Verifier: future adapters without runtime redesign

WAVE 26 — LOCAL_SHELL HARDENING
A: command execution boundary
B: output/evidence
C: cancellation/timeout
Verifier: safe reuse of worker contract

WAVE 27 — EMAIL/FUTURE CONNECTORS
A: permission model
B: read vs consequential action
C: idempotency/retry
Verifier: identify only interfaces needed now

WAVE 28 — LOCAL FILE ORGANIZATION
A: user-selected scope
B: reversible/destructive operations
C: evidence/replay
Verifier: no V1 architecture expansion

WAVE 29 — MOBILE REUSE
A: what mobile should read
B: what mobile may command
C: authentication/session boundary
Verifier: mobile reuses Controller/Ledger truth

WAVE 30 — DESKTOP OVERLAY REUSE
A: event consumption
B: window anchoring boundary
C: robot state
Verifier: overlay remains view-only

WAVE 31 — SCHEMA EVOLUTION
A: event schema versioning
B: projection migration
C: backward compatibility
Verifier: avoid later data migration disaster

WAVE 32 — UPGRADE / RESTORE
A: installer upgrade
B: preserved user data
C: journal backup/restore
Verifier: future-safe local state

WAVE 33 — SECURITY BOUNDARIES
A: localhost/API token
B: filesystem permissions
C: external-adapter permissions
Verifier: future integrations cannot bypass consent

WAVE 34 — SUPPORTABILITY
A: correlation IDs
B: diagnostics bundle
C: replay evidence
Verifier: support without customer terminal work

WAVE 35 — PERFORMANCE REGRESSION
A: startup
B: idle resource usage
C: task throughput
Verifier: future regression budget proposal

WAVE 36 — FINAL FUTURE REWORK FILTER
A: contracts worth preserving now
B: ideas that must be deferred
C: likely future rewrite traps
Verifier: delete speculative work and keep only evidence-backed constraints

Persist BANK 3 synthesis to:
/tmp/courier-v1/factory/BANK3_FUTURE.md

==================================================
FINAL MASTER SYNTHESIS
==================================================

After all 144 child tasks complete, create:
/tmp/courier-v1/factory/MASTER_FINAL.md

Required:
CURRENT_INTEGRATION_HEAD

BANK1_STATUS
BANK2_STATUS
BANK3_STATUS

CHILD_TASKS_TOTAL: 144
CHILD_TASKS_COMPLETED:
CHILD_TASKS_FAILED:
CHILD_TASKS_BLOCKED:

ACTIVE_LEDGER_GAPS
RELIABLE_AUTOMATION_GAPS
GOLDEN_PATH_GAPS
DESKTOP_HUB_GAPS
WINDOWS_EXE_GAPS
CLEAN_MACHINE_GAPS

REAL_DEFECTS
FALSE_ALARMS_REMOVED
CONCURRENCY_RISKS
PROCESS_ORPHAN_RISKS
DATA_TRUTH_RISKS
FALSE_PASS_RISKS
POWER_RESOURCE_RISKS
CUSTOMER_VISIBLE_RISKS

EXACT_OPUS_L2_TASKS
EXACT_OPUS_L3_TASKS
EXACT_OPUS_L4_TASKS
EXACT_OPUS_L5_TASKS
EXACT_OPUS_L6_TASKS

EXACT_L1_MERGE_GATES

FUTURE_CONTRACTS_TO_PRESERVE_NOW
DEFER_UNTIL_AFTER_WINDOWS_EXE

SAFE_IMPLEMENTATION_ORDER

Do not produce the final marker unless all three banks have been reconciled.

FINAL MARKER:
COURIER_144_FACTORY_COMPLETE
```

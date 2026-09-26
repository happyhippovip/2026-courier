# LAST 13% MUSE WALL — ROUND 1

Use this for the final Muse reserve. The goal is not more architecture. The goal is to close the final build + physical-proof blockers with zero interference.

## Usage

- Paste this master ONCE per truly idle Muse window.
- Then use the short CONTINUE prompt up to 10 times per window.
- Do not queue the master repeatedly.
- Do not create a new source writer.
- Stop at IDLE_SAFE when there is no genuinely new work.

## Master prompt

```text
MISSION=COURIER_LAST_13_PERCENT_WALL_ROUND_1
MODE=STRICT_READONLY_FINALIZATION
CONTINUE_BY_DEFAULT=YES
NO_SOURCE_WRITES=YES
NO_RUNTIME_CHANGES=YES
NO_DUPLICATE_WORK=YES

Detect HOST=MAC or WINDOWS.

CURRENT AUTHORITIES:
Windows Antigravity Central Writer = ONLY source writer.
Mac Antigravity = physical probe / physical-proof runner.
Codex = independent final code reviewer.
Opus Ultracode = convergence judge.
Muse = read-only finalization support.

CANONICAL_BASE=
candidate-b-1
4c1e24ccc522042af826bc4c2b595daf85d097f9

REJECTED=
candidate-b-2
83940de3d7d33776a712e7506aa76726d16f8587

TARGET=
final corrected candidate built from b-1.

FINAL WRITER SCOPE IS EXACTLY:
scripts/courier_verifier.py
scripts/integration_contract.py
tests/test_artifact_upload_flow.py
server/app.py
tests/test_p3_server_idempotency.py

TRUST RULE:
expected content hash belongs to trusted task/workflow input.
Never trust worker result for expected hash.

DUPLICATE RULE:
Only the same accepted canonical result for the same attempt/dispatch generation may duplicate-ACK.
Changed status/worker/attempt/dispatch/artifact result must not duplicate-ACK as identical success.

FAILED RULE:
Any FAILED execution invalidates Canary 1.
Do not hide it behind retry.

CURRENT PHYSICAL BLOCKER:
Muse stdout/result contract must be proven in an isolated scratch probe before RUN_1.

CRITICAL PATH:
final candidate + real targeted tests
-> Muse stdout probe
-> exact Mac binding
-> physical A->VERIFY->B
-> deterministic restart/no A replay

==================================================
TASK BANK
==================================================

Choose ONE genuinely unfinished task, then continue to the next free one.

L13-01 Verify new final-candidate SHA/branch consistency across reports.
L13-02 Verify final diff contains only the approved five files.
L13-03 Verify server/app.py contains no unrelated b-2 semantics.
L13-04 Trace trusted task-owned expected hash end-to-end.
L13-05 Check no worker-controlled expected hash remains accepted.
L13-06 Review integrated content-verification tests against the required matrix.
L13-07 Review exact duplicate replay semantics.
L13-08 Review changed-status duplicate negative case.
L13-09 Review changed-worker duplicate negative case.
L13-10 Review changed-attempt/dispatch negative case.
L13-11 Review changed-artifact-result negative case.
L13-12 Validate fixture bytes and SHA256 values exactly.
L13-13 Validate real targeted-test evidence; reject SKIPPED handoffs.
L13-14 Build final candidate handoff checklist.
L13-15 Build Mac isolated binding checklist.
L13-16 Build Muse stdout-probe evidence checklist.
L13-17 Check adapter expected output contract from existing code.
L13-18 Build RUN_1 evidence checklist.
L13-19 Build RUN_1 invalidation checklist.
L13-20 Build RUN_2 restart/no-replay evidence checklist.
L13-21 Detect stale reports referring to b-2/nonfinal candidates.
L13-22 Detect claims that confuse simulated/tested/physical evidence.
L13-23 Detect any claim of universal semantic verification from expected_sha256.
L13-24 Detect any claim of human-relay=0 without physical evidence.
L13-25 Prepare final Proof Card from real evidence only.
L13-26 Prepare Grandma Card from real evidence only.
L13-27 Prepare 60-second demo shell from real evidence only.
L13-28 Prepare first pilot acceptance test; no fake customer/revenue.
L13-29 Prepare customer NO_PERMISSION_SPAM scope rule.
L13-30 Identify exactly ONE remaining blocker capable of stopping the physical gate.

==================================================
ABSOLUTE PROHIBITIONS
==================================================

Do not:
- edit repo source
- git add/commit/apply/merge/reset/clean
- create a competing candidate
- switch another worker's worktree
- start/stop/restart/kill live processes
- start the final Canary
- change settings or permissions
- install dependencies
- invent architecture
- create second wall/scheduler/ledger
- broaden retry semantics
- fake PASS
- fake tests
- fake physical evidence

Use existing code/reports/evidence only.

==================================================
OUTPUT
==================================================

TASK=
STATUS=
NEW_EVIDENCE=
CONTRADICTION=
REPORT=
BLOCKER=
READY_FOR_NEXT_GATE=YES/NO

Then automatically take the next genuinely free useful task.

If no useful work remains:
LAST_13_PERCENT_IDLE_SAFE=YES
STOP.
```

## Continue prompt

```text
CONTINUE_LAST_13_PERCENT

Continue the existing finalization role.
Use only genuinely new evidence.
Skip completed or active work.
No source writes.
No runtime changes.
Prioritize final-candidate validation, Muse-output readiness, RUN_1 and RUN_2 evidence.
If nothing useful remains: LAST_13_PERCENT_IDLE_SAFE=YES.
```

## Round 2 trigger

Do NOT start Round 2 until:
- final candidate SHA exists,
- real targeted tests pass,
- Muse stdout contract is physically confirmed.

Round 2 is reserved for:
physical RUN_1 -> RUN_2 -> visible proof.

# WIN-BB-10 BB10-02 — Revenue verification lane audit (peer's link-11 UNKNOWN, closed)

TREE=fix-cb1-new @ 329abd80. SHELL=DOWN, static only. Closes MUSE-45/WIN-BB-01
open pointer "revenue-lane script behavior (script unread)". Zero test pins
anywhere (name search over tests/*.py = 0 hits for revenue_v1_safety_baseline /
revenue_safety_audit / analyze_workflows / clone_and_extract).

## Lane shape (three pieces, two lanes)

- V1 baseline script scripts/revenue_v1_safety_baseline.py (worker/verify/
  validate_verified_result/reconcile_handoff + CLI). verify() = deterministic
  RE-EXECUTION in verifier_sandbox + report_json_sha256 compare (:100-113).
  Re-execution-as-verification is SAFE here by effect class (SAFE_READ_ONLY,
  :95; git fetch sha-pinned :29) — philosophical split vs backbone
  never-recompute rule is justified, record it. Human gate preserved
  (PR_ONLY :97, HUMAN_REVIEW_REQUIRED :112/:162, human_merge PR check :135).
- Server-task lane: verifier branch courier_verifier.py:114-131 (argv-list
  subprocess, no shell — call shape GOOD) gated on
  `"revenue_safety_audit" in task.get("capabilities", [])` (:114).
- External GHA lane: scripts/intake_dispatcher.py (`gh workflow run
  revenue_v1_baseline.yml` + CWD-local ./central_state.json shadow write
  :40-60 + silent except→empty-state reset :47-48 — HARVESTER
  intake-silent-reset corroborated). Bypasses server claim entirely.

## DEFECTS (Central Writer inputs)

D-BB-8 (MEDIUM, determinism): analyze_workflows uses unsorted rglob
(:38) → findings order OS-dependent → report_json bytes unstable →
verify() (:105) FAILS intermittently (safe direction, availability/noise).
FIX: sort files + findings deterministically. TEST: run worker twice
(fresh dirs) → identical hashes; multi-file fixture with reverse-alphabet
creation order.
D-BB-9 (MEDIUM, false-negative): only `*.yml` inspected (:38); `*.yaml`
workflows SILENTLY uninspected ("No safety violations" while blind). FIX:
inspect both suffixes; record inspected/skipped sets. TEST: .yaml-only
violation fixture must produce findings.
D-BB-10 (MEDIUM, dead lane): revenue_customer_intake posts
{"goal_id","goal_text","tasks":[…]} but /goals reads "workflow_plan"
(app:110) → intake goals fall into the GENERIC PLANNER (3 keyword steps,
revenue fields dropped) while intake prints "Success!". Silent wrong-lane.
Additionally intake omits idempotency_key (worker :88 KeyError → FAIL).
FIX (small, sufficient): intake posts workflow_plan-shaped steps (server
keeps dict steps VERBATIM app:111 incl. capabilities+target_* → claim
passthrough → verifier branch reachable) + adds idempotency_key. Or server
accepts "tasks" alias. TEST: intake-shaped POST → claimed task carries
capabilities+target_*; verifier branch taken.
D-BB-11 (MEDIUM, dormant poison): revenue_worker_adapter registers
["revenue_safety_audit","linux"] (:84) but claim has NO revenue branch
(app:286-290) → "revenue_safety_audit" matches nothing; the "linux" half
DOES match linux tasks → adapter would claim linux tasks and fail them
(worker() KeyErrors on missing target_owner). SAVED TODAY ONLY by a second
bug: adapter expects flat {"task_id":…} (:95) but server returns
{"task":{…}} → every claim misread as empty → idle loop. FIX BOTH TOGETHER
(shape unwrap + linux guard / revenue match branch + task-shape check);
fixing :95 alone ACTIVATES the poisoning. No service wiring starts the
adapter today (deploy/ clean) → dormant until first run. TEST: adapter
against fixture server rejects non-revenue tasks without claiming.
D-BB-12 (LOW, audit precision + robustness): inspected_files keyed by
BASENAME (:39, subdir collisions overwrite); findings reference basename
only (ambiguous); owner/repo interpolated into clone URL unfenced (:26 —
charset-validate [A-Za-z0-9_.-]); non-UTF8 workflow → traceback-FAIL
(fail-closed, noisy); hardcoded happyhippovip PR URL (:144, single-repo).
Bundle fix + pins.

## Verdicts

- Revenue server-task lane: UNWIRED (D-BB-10) + UNPINNED + determinism/extension
  gaps (D-BB-8/9). Do NOT route revenue work here until fixed.
- Revenue GHA lane: external, unexamined for workflow-file existence
  (revenue_v1_baseline.yml presence not checked this package — pointer).
- Writer must PICK ONE lane (server-task vs GHA) and retire/guard the other;
  two half-lanes + one dormant poisoner is the current state.

## Disposition

READ ONLY. No overlap: peer BB-01 scoped revenue out (link-11 UNKNOWN);
MUSE-45 T-old rev only. Next BB-10 gap queued: GHA workflow-file presence +
adapter main-loop tail (:109+) error handling (1 read) if session continues.

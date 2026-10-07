# Google Dual-Host Queue 50 — 2026-09-26

Use the same mission on one Windows Google main worker and one Mac Google main worker.

```text
MISSION=COURIER_GOOGLE_DUAL_HOST_QUEUE_50
MODE=AUTONOMOUS_SEQUENTIAL_CRITICAL_PATH
HOST=AUTO_DETECT
DATE=2026-09-26

WINDOWS_REPO=C:\Users\lol\2026-workspace\2026-courier
MAC_REPO=/Users/user/Downloads/2026-courier

WINDOWS_REPORT_ROOT=C:\Users\lol\courier_work\google_queue_50
MAC_REPORT_ROOT=/Users/user/Downloads/courier_work/google_queue_50

WINDOWS_EVIDENCE_BRANCH=evidence/google-windows-20260926
MAC_EVIDENCE_BRANCH=evidence/google-mac-20260926

GOAL:
Make maximum useful progress toward the first honest physical A -> VERIFY -> B and then deterministic restart/no-replay.

HOST ROLE:
WINDOWS = final candidate source owner.
MAC = physical Canary preparation owner.

GLOBAL:
CONTINUE_BY_DEFAULT
FEATHERLIGHT_BY_DEFAULT
NO_EVIDENCE_NO_PASS
NO_BUSYWORK
UNKNOWN_STAYS_UNKNOWN

NO_NEW_ARCHITECTURE
NO_NEW_LEDGER
NO_NEW_SCHEDULER
NO_NEW_WALL
NO_PRODUCT_SHELL
NO_PACKAGING
NO_SCALE_4_YET
NO_MAIN_MERGE
NO_FORCE_PUSH
NO_RESET_HARD
NO_GIT_CLEAN
NO_ACCOUNT_ROTATION
NO_GITHUB_ACTIONS

Do not ask the human to continue.
If one task blocks, record it and continue independent tasks.
Read existing evidence first.

PRIORITY 0
01 bind branch/SHA/dirty state
02 determine FINAL_MINIMAL_DELTA=B completeness / candidate availability
03 exact changed files / physical process inventory
04 Windows finishes only missing authorized delta; Mac identifies real Muse binary
05 Windows artifact cutover; Mac real Muse CLI flags
06 Windows server-side expected_sha256; Mac adapter comparison
07 Windows duplicate/stale; Mac isolated Canary workspace
08 Windows STARTED/RESULT_READY; Mac ports
09 Windows targeted tests; Mac artifact/state/log paths
10 Windows clean candidate commit+remote handoff; Mac live queue/claim/retry/reconcile/NEXT authority

PRIORITY 1 — TRACE
11 result -> artifact_id
12 artifact_id -> server artifact
13 artifact -> verifier
14 verifier -> verification state
15 verification -> reconcile
16 reconcile -> next READY
17 READY -> worker selection
18 selection -> dispatch
19 dispatch -> STARTED
20 RESULT_READY -> RESULT_RECEIVED

PRIORITY 2 — CONTENT
21 correct expected_sha256
22 wrong content
23 newline variance
24 stale hash
25 empty artifact
26 worker-reported hash cannot self-pass
27 expected_sha256 absent behavior
28 exact Canary A bytes/hash
29 exact Canary B bytes/hash
30 deterministic acceptance

PRIORITY 3 — RECOVERY
31 identical duplicate
32 conflicting duplicate
33 stale attempt
34 stale dispatch
35 result-ID mismatch
36 RESULT_READY resend/lost ACK
37 STARTED ambiguity
38 FAILED requeue
39 new attempt/execution after FAILED
40 side-effect duplication risk

Always distinguish DELIVERY_RETRY from EXECUTION_RETRY.

PRIORITY 4 — PHYSICAL PREP
41 RUN1 state checklist
42 human-relay=0 evidence
43 A execution-count=1 evidence
44 B automatic-start evidence
45 deterministic RUN2 restart checkpoint
46 restart identity comparison
47 abort conditions
48 minimum evidence pack
49 Grandma proof
50 converge to one current decision

WINDOWS FINAL OUTPUT:
FINAL_CANDIDATE_HANDOFF.md with branch/SHA/remote/base/clean/files/scope/tests/patch presence/unknowns/review readiness.

MAC FINAL OUTPUT:
MAC_PHYSICAL_CANARY_HANDOFF.md with local/candidate identity, real Muse binding, runtime processes/authority, isolated workspace/port/storage/logs/resource baseline/blockers/readiness.

PUBLISH reports only to host-specific evidence branch.
Never publish secrets.

Do not wait for all 50 tasks before emitting a critical handoff.
```

# WIN-BB-01 PKG-E — Lane deltas: github verify-stall, antigravity dead-arm, ACK-strengthening note

TREE=fix-cb1-new @ 329abd80 (HEAD, loose ref). SHELL=DOWN (static only). This session ADOPTS
prior-slot PKG-A (five-file trace), PKG-B (16-link backbone), PKG-C (12-case matrix incl BB01-NEW-1),
PKG-D (peer census) — verified by full re-read of all five backbone files + both p3 patches. What
follows is DELTA-ONLY: mac/github lane analysis the prior session explicitly left out (PKG-B link 7:
"Mac/muse differ (cited MW1)"; no github-lane coverage anywhere in A-D).

Files fully read this session for PKG-E: scripts/mac_worker/daemon.py (606L), scripts/github_worker_adapter.py
(179L), scripts/courier_github_dispatcher.py (107L), .github/workflows/courier_worker.yml (143L),
scripts/courier_watchdog.py (42L), deploy/run-supervisor.sh (28L), tests/test_server_integration_contract.py
(415L), tests/test_failure_recovery_matrix.py (98L), tests/test_result_identity_binding.py (50L),
tests/test_artifact_store.py (:85-117 region), docs/p3/server-idempotency-cutover.patch (130L, full).

## BB01-5 MEDIUM — github-lane SUCCESS can never reach RECONCILED (liveness, fail-closed)

CHAIN (all OBSERVED-IN-CODE): workflow runs bounded op on GH-hosted runner, writes
result_{dispatch}.json + courier_output_{dispatch}.json (workflow:60-115), uploads via
actions/upload-artifact (GH-side, :135-143) — NEVER touches Courier POST /artifacts.
Adapter downloads, verifies LOCALLY (hash + per-op acceptance, adapter:75-111), posts
hash-only DurableResult (adapter:114-126, artifacts=[{path,sha256}], no artifact_id), then
DELETES its evidence copy (adapter:166 rmtree). Server accepts → RESULT_RECEIVED (shape-only
validate; check_reference skips hash-only refs). Independent verifier: task target_capability
is "github" (claim sets it from target_agent, app.py:334) → LOCAL lane (verifier:65-69,93) →
local_verify("courier_output_<dispatch>.json", sha) against the VERIFIER's cwd → file missing
(GH runner is remote; adapter deleted its copy) → FAIL → FAILED_VERIFICATION + goal BLOCKED
(app.py:508-510). Resume→retry mints a new dispatch → identical outcome. Permanent stall;
force_success is refused, so no manual completion either.

Repo-wide upload-caller sweep (server/scripts/deploy/.github): POST /artifacts callers are ONLY
windows daemon (upload_artifact :71-99) and mac daemon (http_upload :166-203). Dispatcher claims
with caps ["github"] and never uploads; adapter has zero artifact-store contact. So the designed
server-copy path is structurally unavailable to this lane.

Second facet: the GH lane ignores task artifact expectations entirely — adapter verifies against
downloaded files only, never compares to task.artifacts[]; the dispatch-derived evidence name
("courier_output_<dispatch>.json") cannot satisfy the upload name-in-expected rule
(artifact_store.py:189-191) even if upload were added naively.

CENTRAL_WRITER_INPUT:
FILE=scripts/github_worker_adapter.py FUNCTION=run (post path :157-164) + .github/workflows/courier_worker.yml
DEFECT=github lane posts hash-only results whose evidence exists only on the GH runner; the
independent verifier can never confirm them (local-lane missing-file FAIL), so every github-lane
SUCCESS ends FAILED_VERIFICATION→BLOCKED→retry-loop.
CURRENT_BEHAVIOR=SUCCESS execution → RESULT_RECEIVED → verifier FAIL (missing local file) → goal
BLOCKED → retry reproduces.
REQUIRED_BEHAVIOR=one of: (a) adapter uploads evidence bytes to POST /artifacts BEFORE post_result
and attaches {artifact_id,size} (verifier then re-hashes the server copy — the designed path) —
REQUIRES also solving the name-in-expected mismatch (dispatch-derived evidence name vs plan
expectations: either workflow names evidence per task expectation, or server accepts a
well-formed GH evidence class); (b) document github lane as verify-exempt (weakens independence,
not recommended); (c) co-located verifier with shared evidence workspace (fragile, not recommended).
WHY_IT_MATTERS=whole lane cannot complete autonomously; every github goal stalls BLOCKED with no
recovering action available (retry loops, force refused).
TEST_TO_ADD_OR_RUN=adapter-level: post GH result → run verify_artifacts with production fetch against
empty cwd → expect FAIL today (pins the gap); after fix: upload-then-verify → PASS.
DO_NOT_CHANGE=adapter local acceptance checks (:75-111, strict and correct), deterministic
result_id=result-{dispatch} (crash-safe redelivery), server equality gates, remote-lane refusal.

## BB01-2 LOW — "antigravity" target: claim matches, prepare_task 400s, mac 400-loops (stall, fail-closed)

CHAIN: claim arm exists ("antigravity" in target + cap, app.py:290). Mac daemon registers caps
["macos","linux","antigravity"] (mac daemon:466) — the ONLY worker holding that cap (win hardcodes
["windows"], daemon:47+53, config list explicitly non-authoritative, pinned by
test_windows_worker_contract.py:124-130; dispatcher ["github"]). But WORKER_IDS has no
"antigravity" key (contract:26-31) → prepare_task raises → claim returns 400 (app.py:335-338,
pre-save so no partial mutation persists). Mac daemon treats 400 as claim error → logs → sleeps 5s
→ retries forever (mac daemon:499-502). Task stays QUEUED, goal ACTIVE, never quarantined
(reclaim covers DISPATCHED only) — a silent server-side stall (daemon logs are the only signal).
Planner path never triggers it (planner antigravity→mac mapping, app.py:136, pinned by
test_server_integration_contract.py:214-237); ONLY explicit workflow_plans with antigravity
target_agent do. No test claims an antigravity target (repo-wide search: only the planner-mapping
test + unrelated chief/mjs refs).

CENTRAL_WRITER_INPUT:
FILE=server/app.py (claim :286-290) + scripts/integration_contract.py (WORKER_IDS :26-31)
DEFECT=target vocabulary mismatch: claim matches "antigravity", prepare_task rejects it; verifier
target set {linux,windows,mac,github} (verifier:66) also lacks it. Mac holds a cap it can never use.
CURRENT_BEHAVIOR=explicit-plan antigravity step + mac worker → claim 400 loop, goal stuck ACTIVE.
REQUIRED_BEHAVIOR=either (a) complete the wiring: add "antigravity" to WORKER_IDS (default MAC-01)
and to the verifier target set (lane decision: remote-style upload-required, since mac workers
upload); or (b) remove the claim arm (app.py:290) and the mac "antigravity" cap so the step
cleanly never-matches instead of 400-looping. (a) fits the mac run_agy default mode; (b) fits the
planner's antigravity→mac convergence. Do not leave match-without-accept.
WHY_IT_MATTERS=one goal-shape stalls all mac claim capacity in a 400 loop with no server-side
signal; trivially avoidable either way.
TEST_TO_ADD_OR_RUN=claim with target_agent "antigravity" + mac-cap worker → expect ONE stable
outcome (400 today; 200-or-clean-None after fix — pin whichever the Writer chooses).
DO_NOT_CHANGE=planner mapping, substring-match order for the other four arms, prepare_task strictness.

## BB01-4 INFO — live ACK check (9-field) is STRICTER than the docs/p3 patch (3-field)

The idempotency patch's ACK rule is ("dispatch_id","result_id","status") (patch line 35). Live code
checks 9 fields incl worker_id/run_id/artifacts/attempt_id (app.py:367). Under the PATCH version, a
resend with changed worker_id (same dispatch/result/status) would ACK_DUPLICATE; live code 409s it.
So PKG-C case 10/12 verdicts depend on the post-patch strengthening, which is itself UNPINNED (no
changed-worker-resend test — see PKG-F). Implication for the FINAL gate: if FINAL_SHA is ever minted
from the .patch files rather than the live bytes, case 10 REGRESSES. Prefer live bytes as the mint
source; keep the 9-field rule verbatim. No code change; TEST_TO_ADD rides with case 10 (PKG-F). ADDENDUM: sibling spillover BB01_PKG-E_spillover.md
(BB01-NEW-2 revenue-lane stale contract, BB01-NEW-3 rejected_result accumulation) read after writing;
zero overlap with this file (different lanes). state.json left to the concurrent editor (lists A–E);
my PKG-F/PKG-G are companion files in this dir.

## Mac execution deltas (notes, mostly cited-not-owned)

- run_agy 300s communicate() has NO kill on timeout (mac daemon:304-327, except→FAILED, child
  orphaned) — mac mirror of V-PKG1-1 (which full-read-verified the win file only). run_native echo
  uses subprocess.run with NO timeout at all (:275). Folded as V-PKG1-1 extent, not a new filing.
- Mac registers "linux" cap (:466) → mac-claimed linux tasks verify on the LOCAL lane → inside the
  BB01-NEW-1 exposure surface (adopted, not re-filed).
- Positive (no action): RESULT_PENDING durable-write-before-advance (:557-563), RECOVERY_BLOCKED on
  ENOSPC (:589-592), require_no_orphan + process-group cleanup for MUSE mode (:136-142, :383-389),
  worker-mismatch guards (:429-434, :511-512). Win daemon lacks RESULT_PENDING (direct RESULT_READY)
  — benign asymmetry (crash between persist and deliver redelivers → ACK_DUP).
- Incidental LOW (out of backbone role, hardening note only): run_native allowlist parses only the
  FIRST word (:258-262) but executes the FULL instruction via shell=True (:275) — "echo x; <evil>"
  passes the gate. Self-attack in the current topology (goals are operator-submitted with the worker
  key), latent if task authorship ever broadens. No packet filed; flagging for a security owner.

## Dedupe record

Adopted without re-filing: PKG-A/B/C/D (prior WIN-BB-01), PAYG PKG-1..5, Z04/Z06/Z07, WIN-01
MASTER_6C/MW1, WIN-06 POOL_WIN-004/MW2-MAINT-01, W01-T2-1 (dispatcher relaunch race — dispatcher
full re-read this session is CONSISTENT with it: Popen fire-and-forget :45, blind resume :55-72),
V-PKG1-1/2/4, V-PKG3-1/2, V-PKG4-1/2/3/4. Dropped-as-dup-or-zero-value after verification: my
BB01-1 (== BB01-NEW-1), BB01-3 (upload-time expected check — deferred FAIL reaches the same
BLOCKED+resume outcome as an upload-time 400 path, ~zero practical delta, not filed).

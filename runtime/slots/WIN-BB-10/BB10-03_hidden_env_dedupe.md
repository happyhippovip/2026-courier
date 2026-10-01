# WIN-BB-10 BB10-03 — Hidden-tree census corrections + env/run-evidence assessment

TREE=fix-cb1-new @ 329abd80. SHELL=DOWN, static only. Trigger: live peer
WIN-BB-01 PKG-E cited .github/workflows/courier_worker.yml, which my
default-mode searches could not see → systematic hidden-file recheck
(muse.search `hidden=true`). All verdicts below are the CORRECTED record.

## H1. Hidden census (hidden=true, regex mode)

- .github/workflows/ EXISTS: courier-codex.yml, courier_motor.yml,
  courier_worker.yml, deploy-pages.yml, deploy-static.yml,
  revenue_v1_baseline.yml. (My prior "no .github" negatives are VOID where
  they relied on default-mode globs.)
- .gitattributes: ABSENT even with hidden=true → MW4-12/V-PKG7-4 "no CRLF
  policy" CONFIRMED (now properly evidenced).
- .agents/** + AGENTS.md: ABSENT (corroborates MUSE-45 T-L2).
- .venv/: FULLY PROVISIONED (see H2). .pytest_cache/: lastfailed+nodeids
  present (see H3).

## H2. Environment truth (corrects/refines BB10-01 G0-c)

.venv contains flask 3.1.3, pytest 9.1.1 (+pytest_timeout 2.4.0), requests
2.34.2, werkzeug 3.1.8, waitress 3.0.2, keyring 25.7.0, psutil 7.2.2,
courier_runtime 0.1.0 as EDITABLE install (__editable__ pth+finder,
uv-built). Consequences:
- G0-c REFINED: env EXISTS and is nearly complete; missing ONLY PyYAML
  (no yaml* in site-packages) → test_ci_acceptance_credentials.py
  (`import yaml` :6, safe_load :15) COLLECTION-FAILS even in-venv. FIX: pin
  pyyaml into the env spec (or vendor/drop the dep). G0-a/G0-b (keys at
  collection, ROOT-on-path) STAND unchanged — editable install resolves
  `import scripts/server` to LIVE TREE (scenario "stale installed copy"
  CLOSED; V-PKG2-2 scenario (b) eliminated, scenario (a) stands).
- G0-d (doc drift) stands. New note: pytest_timeout present but
  unconfigured (no timeout marker/ini) — dead weight or future use.
- node (for .mjs) status unknown shell-less — unchanged.

## H3. Run-evidence forensics (NOT counted as pass proof)

- temp/ residue (8 artifact records + rejected_result_w1.json, cite
  V-PKG8-4) + .pytest_cache nodeids listing ALL 15 current upload_flow
  tests (+params) with ZERO upload_flow entries in lastfailed ⇒ the
  upload_flow suite RAN (and was green at that run) under SOME runner/
  revision. Provenance (date/SHA/invocation/keys) UNKNOWN; cache is
  rev-mixed (old-tree suites co-listed), so per NO_EVIDENCE_NO_PASS and
  UNKNOWN≠PASS this is SUPPORTING CONTEXT ONLY. Runner must re-run on
  329abd80 for any verdict above TEST_EXISTS_NOT_EXECUTED.
- lastfailed whole-file entries for test_artifact_store.py,
  test_ci_acceptance_credentials.py, test_muse_convergence.py are
  collection-error-shaped and rev-mixed → INCONCLUSIVE for current tree
  (ci_acceptance coheres with the yaml gap; still unproven).

## H4. BB10-02 addenda (revenue lane)

- D-BB-13 (as drafted: "revenue yml absent") RETRACTED — file EXISTS
  (.github/workflows/revenue_v1_baseline.yml). GHA lane is wired at the
  workflow level (gh call has its target); content unexamined; D-BB-8/9/12
  (script defects) and BB01-NEW-2/D-BB-10/11 (server-task lane dead)
  unaffected.
- Yield record vs live peer WIN-BB-01 PKG-E/spillover (their files):
  D-BB-2 (antigravity dead-arm) YIELDED to peer BB01-2 (theirs is deeper:
  mac 400-loop :499-502 + fix options + verifier-set gap). D-BB-10 intake
  schema + D-BB-11 adapter :95 shape YIELDED to peer BB01-NEW-2 as
  canonical (peer filed first-in-tree + has result-post-shape extension
  :132-140 I had not read). KEPT as distinct: D-BB-1 (result-SET coverage
  vs peer BB01-NEW-1 local-VALUE — complementary), D-BB-3 (stdout loss),
  D-BB-4 (dup task_id), D-BB-5/6 (planner lock-hold/metadata),
  D-BB-7 (courierctl --plan), D-BB-8/9/12 (revenue script), D-BB-11
  poisoning-fix-together warning (extends peer's shape finding).
- Case-8 reload: my INFO-downgrade (stateless-request design) + peer PPR
  (kill-leg pin wanted) COEXIST — design-safe by construction AND pin
  still wanted for the FINAL gate. No contradiction.
- Adopted: peer BB01-4 (9-field live vs 3-field patch ACK — FINAL must
  mint from LIVE BYTES, not .patch files) and BB01-5 (github-lane
  verify-stall; github lane not entered further).

## Disposition

READ ONLY. Retractions/yields recorded above to prevent double-filing.
Next (BB10-04 queued): 12-case PHYSICAL proof procedures (setup/steps/
expected-evidence/forbiddens per case) — unowned synthesis from the
code pins; no new code reads required.

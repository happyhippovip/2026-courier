# T22 RESULT — Branch-harvest inventory (shell-less: ref names + SHAs only)

MODE: LIGHT, read-only. Source: .git/packed-refs (186 refs) + loose refs +
FETCH_HEAD + branch reflog. No diffs possible without git (parked).

## HEAD resolution (OBSERVED)
- .git/HEAD -> refs/heads/ledger-reconciliation-final; loose ref = b927f106
  ("chore(muse-wall): staged scaling proven 1->4->8->16"). packed-refs still
  shows 929fb7e8 for this branch => packed-refs STALE here; loose wins.
- origin/ledger-reconciliation-final = adb9206a = 2nd commit of local history
  => local is ~18 commits ahead of remote (Google Windows work unpushed, or
  pushed elsewhere; needs fetch to resolve — parked, no push from here).
- origin/main = 3e2fe24d. Local main: no loose ref; packed e7d047d9 stands
  (AMBIGUOUS: possibly deleted locally with stale packed entry).
- Coordination seed branch: loose ref only (73770a5b), absent from packed-refs.

## Sync snapshot (local vs origin, notable)
IN SYNC: courier/windows-phase-15-completion (6f428721), safety-hardening
(24b3a4f), phase-a/b/c, feature/external-end-to-end, feature/worker-adapters,
feature/github-actions-adapter, happyhippovip-github-automation-integration,
pr42==origin/codex/canonical-physical-proof-harness (e074ed39),
pr43==origin/codex/ledger-truth-finish (cd839d1a).
DIVERGED/AHEAD: ledger-reconciliation-final (above), release-candidate-
integration (local d344c0b6 vs origin 71b3dc06), feature/worker-bootstrap
(local 062ecc0c vs origin 80bbc50b), main (above).
NO-OP/DUP REFS: muse/run-20260925-HARVEST-A-slot-04 == origin/main (3e2fe24d,
no unique commits); finish-cb3 == courier/phase-c-server-hosted-repair
(dc03c250); known-good tag == origin/known-good/1-10 (6ca172ac, consistent).

## Harvest shortlist (by mission relevance; diffs need shell)
1. courier/process-safety-requirements — process-safety rung.
2. muse/MUSE-A01-duplicate-guard-failclosed + MUSE-A01-adapter-double-exec-guard
   — duplicate-execution rung (DISPATCHER context).
3. muse/MUSE-A01-provider-wait-isolation — WAITING_PROVIDER rung.
4. courier/codex-verifier-authority + courier/codex-stale-effect-quarantine —
   verifier rung (VERIFIER_review context).
5. supervisor/canonical-muse-runtime + supervisor/wall-slot-restart — wall rung.
6. claude/task09-thought-tests-portable — portability rung (T9 context).
7. courier/heavy-process-supervisor + codex/motor-eligibility-v1 — motor rung.
8. codex/canonical-physical-proof-harness + codex/ledger-truth-finish — RC proof
   rung (already mirrored as local pr42/pr43).
9. muse/MUSE-A01-resource-policy-escapes + runbatch-sha-failclosed +
   storage-contract — safety-policy rung.
10. muse/run-20260925-HARVEST-A-slot-01/02/03/05 + claims/* (7 refs) — prior
    harvest outputs; read before re-harvesting (dedupe).

## Shell-back method (parked, for owner/runner-alive session)
For each candidate: git log --oneline origin/<X> ^b927f106 (unique commits);
git diff --stat b927f106...origin/<X>; cherry-pick only with writer scope.
NO merges/checkouts performed here (also impossible: no shell).

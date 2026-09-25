# Cannon V1 repository acceptance

Scope: the Cloud HTTP candidate `staging/cannon-v1-candidate` at
`e6a5a53a74ae457523eba72e6aeaacada97b65f3`. This is **not** the divergent
`app/cannon` / local Motor branch family, and **not** physical acceptance.
No architecture, runtime, worker, credential, launcher or ledger changes here.

## One command

From the checkout root, with Python 3.9+ and the existing pytest/Flask/requests dependencies:

```sh
python3 scripts/acceptance/run_final_acceptance.py --repo --output /tmp/courier-cv1-new-run.json
```

Use a new output filename each time; existing evidence is never overwritten.
Without `--repo` the existing entry point refuses with exit 2. The obsolete
synthetic-traffic mode is removed, not moved to a second harness.

Exit 0 = required repository matrix passes, **never physical PASS**.
Exit 1 = an executable invariant fails. Exit 2 = refused/incomplete/unsafe proof.
No skip, xfail, xpass, collection failure or unexecuted case counts as PASS.
Each parameterized case and teardown outcome is included in the JSON evidence.

For targeted red/green, append e.g. `--only CV1-DUR-004`. Unselected rows remain
NOT_PROVEN; a passing subset cannot produce a full repository PASS.

## Safety and proof boundaries

- Original checkout and Cloud candidate are untouched; this branch contains only
  the repaired entry point, acceptance tests, matrix and evidence.
- Child test process inherits **no real credentials**. Only test-only values,
  temporary state and `.invalid` endpoints are supplied. No Keychain access.
- Network connects/binds, shell commands and unexpected subprocesses are blocked.
  The only subprocess exceptions are the existing temporary P3 patch fixture and
  the no-opt-in refusal test. The urllib3 import-time IPv6 probe is disabled.
- Server tests use Flask's in-process client with explicit workflow plans; the
  unused provider planner import is blocked. Native execution/PowerShell and
  transport are fixture doubles. No daemon, provider, pipeline or live goal starts.
- Test process is bounded to 120 seconds. No broad process cleanup.
- All selected Python source fingerprints are recorded before/after. SHA and
  matrix establish the proof version; changing product code requires a new run.
- Component artifact tests are not integrated artifact-flow proof. P3 tests apply
  `docs/p3/artifact-upload-cutover.patch` to a temporary server copy only and are
  labelled PREVIEW_PASS. Separate tests reuse the same flow **without** that patch.
- File fsync/atomic replace and module reload are repo proofs, not sudden power
  loss, OS service ownership, real external effects or real Windows runtime.

## Reproduced integration gaps (owner: Cloud/worker integration lane)

1. **CV1-DUP-002:** identical completed packet redelivery executes the same
   attempt again on both workers. Server single-flight passes, but is not a
   worker-local replay guard. Fake transport explicitly injects redelivery;
   this is not a claim that the current healthy server spontaneously redelivers.
2. **CV1-DUR-004:** injected RESULT_READY persistence failure is logged, but the
   next loop sends the in-memory result without successful persistence on both
   workers. Normal persistence-before-send and stored-result recovery pass.
3. **CV1-IDEMP-001/002:** identical FAILED resend after requeue gets HTTP 400;
   contradictory SUCCESS replay gets HTTP 200 instead of rejection. First stored
   result remains unchanged; the defect is the acknowledgement contract.
   Existing `c9259d92` addresses part of this. Its three-field duplicate equality
   is insufficient for altered artifact/worker/attempt fields (code inspection,
   not an executed proof against that branch). Reuse/extend the fix, do not rewrite.
4. **CV1-ART-003:** SUCCESS carrying an unrelated artifact name is accepted despite
   the dispatched expected-artifact list. Shape-valid hash evidence is insufficient.
5. **CV1-ART-004/007:** real candidate has no `/artifacts` route. With upload enabled,
   both worker flows reach HUMAN_REQUIRED after HTTP 404 instead of verification.
   Preview patch flow passes. Cloud owns cutover; workers also need upload enabled.

These are genuine red acceptance tests, not xfails or automatic repair requests.
No product fix was attempted because Cloud owns the candidate and relevant work
already exists. The JSON branch review records 19 pinned branch classifications.

## Required physical evidence, after repository gaps are closed

The Mac and Windows owners must supply exact server/worker SHAs and a continuous,
OS-owned run: one real canonical Goal, at least ten eligible completed tasks,
at least two real workers, automatic result -> independent verifier -> reconcile
-> next dispatch, including interruption/resume and an external-effect crash
boundary. Require zero manual continuation/restarts, duplicate external effects
and leftover task-owned processes, then genuine DONE -> CLEAN_IDLE.
Persisted-result resend and ambiguous STARTED recovery must also be demonstrated
with actual worker processes. Neither this report nor Cloud simulations replace
those proofs. No physical PASS is emitted by this entry point.

## Handoff

- `cannon_v1_matrix.json`: executable selectors, expected behavior and proof tiers.
- `cannon_v1_branch_review.json`: ancestry/patch reuse and parked incompatible work.
- `cannon_v1_evidence.json`: fixed-candidate run, individual outcomes and source hashes.
- Integrate through the owning Cloud lane, rerun the same command on its new fixed
  SHA, then collect physical evidence. Do not merge this red candidate into main.

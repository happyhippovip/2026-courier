# MMAC-200 — #217/#218 genuine, #219 executor-gap finding (WINDOW 3, read-only)

Base `origin/integration/v1` = `f425d328`. Zero mutations.

## #217 repo-reality credential scrub: VERIFIED genuine
Without the fix, credential-shaped values on flagged source lines reached the customer report verbatim (or nuked it via the refusal tripwire). `scrub_credential_shapes` redacts in place; the test runs the real `check()` + `main()` on a scratch repo with a fake token and asserts absence from both finding detail and `report.json`. Residual note (below fix threshold, no patch): truncation `[:120]` happens before scrubbing, so a token straddling the cut leaks an unmatchable fragment — partial-fragment only, brute-force-infeasible remainder, owner may harden by scrub-then-truncate.

## #218 poison_test residue deletion: VERIFIED safe
One-line stub file removed; full CI (pytest + acceptance, ubuntu + windows) green without it. No action.

## #219 host-budgets checkpoint contract: UNPROVEN contract-half (finding, no patch)
`plan_hibernation` returns `"keep_checkpoint_service": True` yet, on RESOURCE_PAUSE/EMERGENCY, lists every non-hibernated lane id — checkpoint service included — under `hibernate`, with no service lane-id marker in the plan. The module executes nothing itself; the executor that must honor the flag was not located this session, so fulfillment of the documented sparing obligation is unproven. Flag dates to d8c413457 (Issue #76); #219 only reworded the docstring. Owner next step: locate the plan executor and prove emergency sparing, or promote the service lane id into the plan dict so the obligation is actionable. No patch from here — the defective half (if any) lives in an unlocated executor, and the planner cannot filter by an id it declares unknown.

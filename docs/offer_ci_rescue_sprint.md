# CI Rescue Sprint playbook

**Price:** €390 fixed
**Goal:** Take a broken, red, or severely unreliable CI pipeline and deliver a perfectly green build on a clean runner.

## Scope
1. **Diagnosis:** We investigate the root cause of the broken CI pipeline.
2. **Environment Classification:** We separate true product code bugs from environment/runner failures (e.g. pinned dependencies, network timeouts, stale cache).
3. **Fix Implementation:** We supply a pull request with targeted fixes.
4. **Verification:** The fix is verified to pass all tests on a clean runner without warnings or errors.

## PR Etiquette
- All PRs are strictly limited in scope to the CI fix itself. No random linting or refactoring unrelated to the failure.
- Detailed explanation in the PR description, explicitly stating *why* it broke and *how* the fix resolves it.
- Never force-push or rebase against active customer branches without explicit request. 

## Definition of Done
The service is complete when:
- A PR is delivered to the customer.
- The CI pipeline associated with the PR passes 100% on a clean runner ("green on clean runner").
- A brief final report explains what changed and how to prevent the issue from recurring.

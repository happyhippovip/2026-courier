# MMAC-199 — #215 genuine, #216 partial with owner-ready evidence (WINDOW 3, read-only)

Base `origin/integration/v1` = `f425d328`. Zero branch mutations (one red probe executed, then discarded with its worktree).

## #215 budget-alert: VERIFIED genuine
Old script printed `Budget check: OK. Under €2.00.` unconditionally — a false budget guarantee a cost gate could mistake for a passing check. Fix converts it to a fail-closed stub (exit 2, "STUB" on stderr). Tests execute the real script via subprocess (non-zero return, no "OK" on stdout, import side-effect-free). No action.

## #216 ci-truth: PARTIAL, no patch (deliberate)
The cleanup is real: removes a dead `git archive` run whose piped output nobody read (pipe-buffer stall risk). The "verify bounds" half is mock-only — `tests/test_ci_truth.py` patches `subprocess.run`/`Popen` for every stage, so the real archive→tar pipeline has zero executable coverage.
- Probative red test (scratch repo + bogus SHA): on Linux this would raise CalledProcessError and skip `archive_proc.wait()` (transient zombie); on THIS Mac BSD tar exits 0 on empty stdin and execution slides into `FileNotFoundError: 'docker'`. Either way the module's error-dict contract is violated for the extract stage — but no fix ships from here: without docker in the loop the contract is unobservable end-to-end, and an unprovable change is worse than a documented gap.
- Mitigating fact: `repo_reality_check.py:229-233` already try/excepts `run_ci_truth` into an error dict — no caller crash today.
- Owner-ready smallest fix: try/finally `wait()` + extract-stage error dict, proven on a docker-equipped host. Branch `muse/MUSE-ledger-ci-truth` left untouched for its owner.

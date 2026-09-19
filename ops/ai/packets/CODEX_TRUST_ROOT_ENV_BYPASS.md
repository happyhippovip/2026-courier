# Codex Trust Root acceptance blocker

STATUS: REPRODUCIBLE_DEFECT
REVIEWED_HEAD: d5cd013033156657630ccaa7f8017ab1f842c686
OWNER: GOOGLE (Ledger/Guard/Motor production scope)
CODEX_SCOPE: independent review only

## First causal defect

`scripts/agent_handoff_ledger.py::_verify_attestation` returns `True` for every
URL whenever the caller-controlled process environment contains
`PYTEST_CURRENT_TEST`. This is not a trustworthy test seam: the environment
variable can be set in an ordinary process, so an unreachable or nonexistent
receipt is promoted as verified.

## Deterministic reproduction

```sh
PYTEST_CURRENT_TEST=attacker-controlled python3 - <<'PY'
from scripts.agent_handoff_ledger import _verify_attestation
print(_verify_attestation('https://invalid.example/no-receipt'))
PY
```

Observed: `True`

Expected: `False`

## Adjacent contract failure

The current authenticated-receipt evidence carries `result_sha256`, but
`validate_guard` rejects that field. The targeted acceptance run therefore
finishes with 22 failures and 46 passes before the receipt can be consumed.

Command:

```sh
python3 -m pytest -q \
  tests/test_ledger_attestation_trust_root.py \
  tests/test_ledger_authenticated_receipts.py \
  tests/test_ledger_self_cert_rejection.py \
  tests/test_ledger_freshness_binding_epoch.py \
  tests/test_ledger_freshness_rejection.py \
  tests/test_attestation_cross_defect_crash.py \
  tests/test_ledger_duplicate_semantics_contract.py
```

## Minimum Google repair

1. Remove the `PYTEST_CURRENT_TEST` authority bypass from production code.
2. Inject a verifier/receipt resolver explicitly in tests, defaulting production
   to fail closed; a process environment string must never grant attestation.
3. Make the schema and authenticated receipt contract agree on the bound result
   digest (`result_sha256`), then validate that digest rather than discarding it.
4. Retain exact URL, SHA, runtime, producer principal, verifier principal,
   freshness, epoch, and task/result lineage checks.

## Mandatory regression tests

- Setting `PYTEST_CURRENT_TEST` in a normal process does not validate an invalid URL.
- Network/authority failure returns untrusted and cannot advance the Ledger.
- A genuine authenticated receipt with matching `result_sha256` is accepted.
- Changed digest, URL, runtime, SHA, principal, epoch, or lineage is rejected.
- Same-update and multi-update self-certification remain rejected.

## Unchanged accepted evidence

The independent false-green/edge-conservation batch remains green on this
checkout: 13 passed in 2.07s. It does not close this Trust Root defect.

Provider-wait isolation and cluster-lock regression remain green independently:
5 passed in 1.05s (`test_provider_wait_isolation.py`, `test_provider_wait.py`,
`test_global_queue_stall.py`). INIT/same-update and false-CLEAN-IDLE targeted
guards also remain green: 2 passed in 0.26s. These decisions can be reused;
Google only needs to repair and return the Trust Root delta above.

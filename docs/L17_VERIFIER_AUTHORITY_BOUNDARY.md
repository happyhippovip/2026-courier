# L17 VERIFIER AUTHORITY BOUNDARY

## Objective
Prove that a verifier cannot create arbitrary authority or spoof its identity during canonical verification. 

## Findings
The Ledger structurally protects the verifier authority boundary during `run_verifier`. Even if a malicious or broken adapter returns a `Verdict` object containing spoofed `verifier` identity data (e.g., attempting to claim `"kind": "admin"` or escalate privileges), the controller completely overrides this data.

In `courier_core/verification.py`:
```python
    identity = verifier_identity(verify)
    ...
    return replace(verdict, reason=str(verdict.reason)[:500], retryable=bool(verdict.retryable), verifier=identity)
```
The `verifier_identity` function derives the true identity using static Python module reflection (`__module__`, `__qualname__`) and a cryptographic SHA-256 digest of the verifier's source code file. The adapter's output is forcibly rebuilt using `dataclasses.replace`, permanently stripping any spoofed authority.

The controller therefore maintains absolute authority over the metadata appended in the `RESULT_ACCEPTED` journal event.

## Validation
I created `tests/controller/test_l17_verifier_authority.py` to explicitly simulate a verifier returning a spoofed `verifier` dictionary (`root_overlord`). The test proves deterministically that the resulting `RESULT_ACCEPTED` event in the journal contains the controller-derived identity, ignoring the adapter's spoofed authority. No implementation changes are required.

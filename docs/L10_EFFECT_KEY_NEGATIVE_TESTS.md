# L10: EFFECT_KEY_NEGATIVE_TESTS

## Objective
Attack the proposed `effect_key` provider-idempotency conformance gate (L09) with a suite of synthetic negative tests to prove it rigorously drops invalid, missing, or mismatched keys.

## Analysis
To safely accept `RESULT_READY` payloads, the controller's Verifier relies entirely on cryptographic and deterministic checks over the evidence in the `home` directory. The provider's receipt serves as the proof that the exact `effect_key` was handed over to the external system.

The negative test matrix implemented in `tests/test_l10_effect_key_negative.py` introduces the L09 `strict_verify` monkeypatch and subjects it to the following attacks:

1. **Missing Receipt**: Adapter succeeded but forgot to write `receipt.json`.
   - **Result**: Rejected ("evidence lacks provider-idempotency conformance proof").
2. **Malformed Receipt**: Adapter wrote `receipt.json` but it's corrupted/non-JSON.
   - **Result**: Rejected.
3. **Missing Key in Receipt**: `receipt.json` is valid JSON but lacks the `effect_key` field.
   - **Result**: Rejected.
4. **Mismatched Key**: Adapter wrote `receipt.json` with an old/different `effect_key` (e.g. `cfx-222` instead of `cfx-111`).
   - **Result**: Rejected.
5. **Success Control**: Adapter correctly writes `{"effect_key": "cfx-111"}` inside `receipt.json` and hashes it into the artifacts payload.
   - **Result**: Accepted.

## Implementation Handoff (Fix Packet)
The deterministic test suite `tests/test_l10_effect_key_negative.py` has been committed to branch `ledger/L10-effect-key-negative-tests`.

These tests prove that the L09 structural fix is bulletproof. The target writer must fold these test cases directly into `tests/test_synthetic_adapter.py` alongside the main `verify` tests to ensure the conformance gate never regresses.

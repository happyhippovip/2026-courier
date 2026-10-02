# L09: EFFECT_KEY_CONFORMANCE_GATE

## Objective
Define and implement the provider-idempotency conformance contract. Every adapter must mathematically prove to the L2 Verifier that it passed the exact `effect_key` to the provider. The Verifier must strictly reject evidence lacking this proof.

## Analysis
The L08 fix packet ensured that `effect_key` is passed into the adapter's `run()` function. However, the L2 Verifier currently has no conformance gate: it accepts successful outcomes even if the adapter completely ignored the `effect_key` (as proven by the red test in `tests/test_l09_effect_key_conformance.py`). 

Without this gate, a rogue or buggy adapter could run a non-idempotent task multiple times on the provider side by failing to pass the idempotency key, entirely bypassing the system's L2 guarantees.

## Implementation Handoff (Fix Packet)

### 1. Adapter Execution Must Embed the Key
When an adapter runs, it must retrieve a provider receipt that embeds the idempotency key. For the `synthetic` adapter, we simulate this by writing a signed `receipt.json` alongside the primary artifact.

**File: `adapters/synthetic.py` (in `run`)**
```python
<<<<
    data = cfg["content"].encode("utf-8")
    _atomic_write(root / cfg["write"], data)
    digest = hashlib.sha256(data).hexdigest()
    return RunResult("success", [{"path": cfg["write"], "sha256": digest, "size": len(data)}])
====
    data = cfg["content"].encode("utf-8")
    _atomic_write(root / cfg["write"], data)
    digest = hashlib.sha256(data).hexdigest()
    
    # Provider-idempotency conformance: The provider receipt must echo the effect_key.
    receipt_data = json.dumps({"effect_key": effect_key}).encode("utf-8")
    receipt_path = "receipt.json"
    _atomic_write(root / receipt_path, receipt_data)
    receipt_digest = hashlib.sha256(receipt_data).hexdigest()
    
    return RunResult("success", [
        {"path": cfg["write"], "sha256": digest, "size": len(data)},
        {"path": receipt_path, "sha256": receipt_digest, "size": len(receipt_data)}
    ])
>>>>
```

### 2. Verifier Must Gate on the Key
The verifier must extract the receipt and assert that the provider processed the exact `task.effect_key`. If the key is missing or mismatched, it must reject.

**File: `adapters/synthetic.py` (in `_verify`)**
```python
<<<<
    if pinned and not seen_pinned:
        return _reject("declared synthetic artifact is absent from the evidence")
    return _accept("synthetic evidence verified")
====
    if pinned and not seen_pinned:
        return _reject("declared synthetic artifact is absent from the evidence")

    # EFFECT_KEY CONFORMANCE GATE
    expected_key = getattr(task, "effect_key", None)
    if expected_key:
        receipt_found = False
        for ref in artifacts:
            name = ref.get("path")
            if name.endswith("receipt.json") or name == "receipt.json":
                try:
                    receipt_data = json.loads((scope / name).read_bytes())
                    if receipt_data.get("effect_key") == expected_key:
                        receipt_found = True
                        break
                except (OSError, ValueError):
                    pass
        if not receipt_found:
            return _reject("evidence lacks provider-idempotency conformance proof (effect_key mismatch or missing receipt)")

    return _accept("synthetic evidence verified")
>>>>
```

## Evidence & Verification
A red test `tests/test_l09_effect_key_conformance.py` has been committed to `ledger/L09-effect-key-conformance-gate`. It constructs a task with an `effect_key` and provides evidence that omits the conformance receipt. The test proves that the L2 Verifier currently accepts this incomplete evidence. Applying the fix packet turns the test green by making the verifier strict.

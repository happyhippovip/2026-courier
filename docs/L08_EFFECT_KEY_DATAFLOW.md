# L08: EFFECT_KEY_DATAFLOW

## Objective
Trace `effect_key` from the task definition down to the adapter boundary, locate where it is dropped, and provide an implementation-ready fix to ensure adapters receive the idempotency key for provider-side conformance.

## Analysis
The `effect_key` originates in `courier_core/events.py` (via `task.task_id`) and flows correctly through:
1. `controller.py` -> `serve.py` (claim payload)
2. `service.py` (spec parsing)
3. `adapter_bridge.py` (validation and JSON serialization)
4. The worker host L3 `request.json` file on disk.

**The Drop Point:**
In `courier_worker/adapter_runner.py` (the trusted lane L3 runner), the JSON is parsed and `request["effect_key"]` is successfully deserialized (or silently ignored). However, when L3 calls into the actual adapter (L4 code), the execution is written as:
```python
result = synthetic.run(params, workdir, attempt)
```
The `effect_key` is dropped entirely at this exact line.

## Implementation Handoff (Fix Packet)

### 1. Update the L3 Adapter Runner
The L3 runner must extract the `effect_key` from the `request` envelope and explicitly pass it as a keyword argument to the adapter's `run()` function.

**File: `courier_worker/adapter_runner.py`**
```python
<<<<
    from adapters import synthetic

    try:
        result = synthetic.run(params, workdir, attempt)
    except synthetic.SyntheticHang:
====
    from adapters import synthetic
    
    effect_key = request.get("effect_key")

    try:
        if effect_key is not None:
            result = synthetic.run(params, workdir, attempt, effect_key=effect_key)
        else:
            result = synthetic.run(params, workdir, attempt)
    except synthetic.SyntheticHang:
>>>>
```

### 2. Update the Adapter Interface Contract
Adapters must be modified to accept the `effect_key`.

**File: `adapters/synthetic.py` (and all future adapters)**
```python
<<<<
def run(params: Mapping[str, Any], workdir: str | os.PathLike, attempt: int = 1) -> RunResult:
====
def run(params: Mapping[str, Any], workdir: str | os.PathLike, attempt: int = 1, effect_key: str = "") -> RunResult:
>>>>
```

## Evidence & Verification
A red test has been authored and committed to branch `ledger/L08-effect-key-dataflow` (`tests/test_l08_effect_key_dataflow.py`). It mocks the adapter's `run()` function to capture its `kwargs` and asserts that `effect_key="cfx-12345"` is received when `adapter_runner.main()` executes.

Applying the two diffs above turns the red test green, successfully piping the `effect_key` from the L2 controller all the way to the L4 provider adapter, unlocking the next step: L09 provider-side conformance gates.

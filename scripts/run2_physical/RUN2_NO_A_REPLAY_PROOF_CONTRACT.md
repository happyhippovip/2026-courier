# RUN 2 NO-A-REPLAY PROOF CONTRACT

## Verification Requirement
RUN 2 must NEVER re-execute Process A, as its state was perfectly transferred via the durable state snapshot from RUN 1.

## Data Sources
1. RUN 2 Execution state log: `run2_state_snapshot.json`
2. Metric target: `$.execution_counters.process_a`

## Verification Rule
```python
def verify_no_a_replay(run2_snapshot_path):
    import json
    with open(run2_snapshot_path) as f:
        data = json.load(f)
    
    # Process A execution counter in RUN 2 specifically must be exactly 0
    a_count = data.get('execution_counters', {}).get('process_a', -1)
    assert a_count == 0, f"Process A was replayed in RUN 2! Expected 0, got {a_count}."
```

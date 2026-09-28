# RUN 2 EXECUTION COUNT PROOF CONTRACT

## Verification Requirement
RUN 2 must only execute B exactly once, and since A was not executed in RUN 2, the combined global execution count (for a successfully resumed process) over the entire span of RUN 1 + RUN 2 must be EXACTLY 1 for `A` and 1 for `B`.

## Data Sources
1. RUN 1 Execution state log: `run1_state_snapshot.json`
2. RUN 2 Execution state log: `run2_state_snapshot.json`

## Verification Rule
```python
def verify_global_execution_counts(run1_snapshot_path, run2_snapshot_path):
    import json
    
    with open(run1_snapshot_path) as f:
        run1 = json.load(f)
    with open(run2_snapshot_path) as f:
        run2 = json.load(f)
    
    # Run 1 stats
    r1_a = run1.get('execution_counters', {}).get('process_a', 0)
    r1_b = run1.get('execution_counters', {}).get('process_b', 0)
    
    # Run 2 stats
    r2_a = run2.get('execution_counters', {}).get('process_a', 0)
    r2_b = run2.get('execution_counters', {}).get('process_b', 0)
    
    total_a = r1_a + r2_a
    total_b = r1_b + r2_b
    
    assert total_a == 1, f"Process A global execution count was {total_a}, expected exactly 1."
    assert total_b == 1, f"Process B global execution count was {total_b}, expected exactly 1."
    
    # For correctness
    assert r1_a == 1, "A should have run in RUN 1"
    assert r2_a == 0, "A should NOT have run in RUN 2"
```

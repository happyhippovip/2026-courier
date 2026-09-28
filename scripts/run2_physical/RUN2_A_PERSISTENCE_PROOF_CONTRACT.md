# RUN 2 A PERSISTENCE PROOF CONTRACT

## Verification Requirement
RUN 2 must boot up and immediately recognize the fully verified `A` state persisted from RUN 1 without re-executing `A`.

## Data Sources
1. RUN 2 Execution state log: `run2_state_snapshot.json`
2. Metric target: `$.initial_state.process_a_status`

## Verification Rule
```python
def verify_a_persisted(run2_snapshot_path):
    import json
    with open(run2_snapshot_path) as f:
        data = json.load(f)
    
    # Process A state must be loaded as 'COMPLETE' from the initial payload boot
    a_status = data.get('initial_state', {}).get('process_a_status', 'UNKNOWN')
    assert a_status == 'COMPLETE', f"Process A state was not durably recovered. Expected 'COMPLETE', got '{a_status}'."
```

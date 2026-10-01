# M223: Runner Durability

## Goal
Prove that the native worker daemon maintains durable internal state, allowing it to survive unexpected interruptions without corrupting the wider system.

## Implementation & Proof
1. **Local Disk Persistence**:
   - `daemon.py` writes its progression strictly to a file on disk: `state/current_task.json`.
2. **Atomic Writes**:
   - The helper function `persist_task` performs a durable write pattern:
     ```python
     with open(tmp_path, "w") as f:
         json.dump(task, f)
         f.flush()
         os.fsync(f.fileno())
     os.replace(tmp_path, path)
     ```
   - This prevents partial corruption during a mid-write power failure. 
3. **Resiliency**:
   - When the script reloads, it resumes from the EXACT state (e.g., `"CLAIMED"`, `"STARTED"`, or `"RESULT_READY"`), ensuring it knows whether execution crossed the effect boundary or not.

## Conclusion
Courier physically prevents torn-state errors in the worker node via strict filesystem syncs and atomic renaming.

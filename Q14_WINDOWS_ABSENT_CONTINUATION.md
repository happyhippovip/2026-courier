# Q14 — WINDOWS-ABSENT CONTINUATION

**Objective**: Prove that if the Windows worker is absent, Courier does not hang or block the rest of the queue.

**Execution**:
1. Added `q14_proof.py` to orchestrate a test where both a Windows goal and a Linux goal are queued.
2. The central state is flushed, simulating a fresh start.
3. Only the Linux worker registers and begins polling.
4. The Windows worker is entirely absent.

**Results**:
- The Linux worker successfully claimed its task (`linux` target) in the queue, skipping the blocked Windows task.
- Subsequent claims correctly returned no tasks for the Linux worker, while the Windows task safely remained in the queue for when the Windows worker returns.
- System continued executing without blocking on the missing capability.

**Acceptance Status**:
- `WINDOWS_ABSENT_CONTINUATION = PASS`
- No manual queue intervention was needed.

Test committed as `scripts/q14_proof.py`.

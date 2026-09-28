# MAC-FINISH-10 — Replay Equivalence Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-10
- **Area**: REPLAY_EQUIVALENCE_PACKET
- **Status**: COMPLETE

Verifies restart resilience and side-effect idempotency: an interrupted coordinator restarts and resumes work without re-executing previously completed tasks.

---

## 2. Test Harness Sequence
1. Task A executes and achieves `RECONCILED`.
2. Server process is abruptly interrupted via `kill -TERM`.
3. Server restarts pointing to the exact same `STATE_DIR`.
4. Server parses `central_state.json`:
   - Recognizes Task A as `RECONCILED`.
   - Bypasses Task A completely.
   - Evaluates next unblocked tasks and immediately dispatches Task B.

---

## 3. Equivalence Invariants
- `task_a_replayed == FALSE`
- `task_a_attempts_post_restart == 1`
- `task_b_dispatched == TRUE`

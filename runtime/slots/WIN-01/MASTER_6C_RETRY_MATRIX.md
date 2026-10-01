# §6C — FAILED / RETRY / SIDE-EFFECT matrix (READ_ONLY_PREP)

Staged in-slot (REPORT_ROOT outside writable roots; operator copies).
No code writes. Grounding: current `server/app.py`, `scripts/
integration_contract.py`, `scripts/windows_worker/daemon.py`,
`scripts/mac_worker/{daemon.py,muse_adapter.py,runtime_state.py}`.

Headline rule: a new `attempt_id` authorizes a new EXECUTION, never a
repeated SIDE EFFECT. Nothing in TaskPacket marks instructions as
side-effect-free (`prepare_task` carries identity/status/artifacts only,
integration_contract.py:43-63) — so every re-execution path below must be
read as UNSAFE for non-idempotent effects unless its row says otherwise.

## Matrix

1. DELIVERY RETRY (same dispatch_id+result_id+status resend)
   WHEN_SAFE=always. Server ACK_DUPLICATEs (app.py:367-368); both workers
   redeliver the identical persisted RESULT_READY payload (win:113-135,
   mac:205-217). No re-execution anywhere on this path.

2. EXECUTION RETRY after worker FAILED (attempts<3 → QUEUED, app.py:388-390)
   WHEN_SAFE=instruction is idempotent (re-runnable without added effect).
   WHEN_UNSAFE=non-idempotent real effect (file/service/external mutation):
   next claim mints a FRESH attempt_id/dispatch_id (app.py:329-333) and the
   worker executes the instruction from scratch with no memory of the prior
   attempt's effects. The fresh IDs prevent result confusion, NOT effect
   duplication. WHEN_UNKNOWN=any task whose instruction was not classified.

3. NEW ATTEMPT after resume (FAILED_VERIFICATION/FAILED_TERMINAL/
   HUMAN_REQUIRED → retry → QUEUED, app.py:534-545)
   WHEN_SAFE/UNSAFE=same as (2). Old results cannot bind (fresh IDs,
   app.py:535-536 + contract:138-140), but old EFFECTS are not tracked —
   resume re-executes blindly. `force_success` is refused (546-549): no
   result without dispatch+verifier. GOOD.

4. TIMEOUT ORPHAN + server retry (Windows)
   WHEN_UNSAFE=always. Windows converts timeout→FAILED (daemon.py:211-220)
   and leaves the child RUNNING (no kill path in worker code); server
   retries (row 2) while the orphan may still act → duplicate-effect
   window. Mac/MUSE instead releases without result + verified cleanup
   (MW1 D1) — the two platforms disagree on this row.

5. VERIFIER FAIL → FAILED_VERIFICATION + goal BLOCKED (app.py:508-510)
   WHEN_SAFE=structurally: terminal until explicit resume; no automatic
   re-execution. Resume re-enters via row 3 rules.

6. attempts>=3 → FAILED_TERMINAL + goal BLOCKED (app.py:391-404)
   WHEN_SAFE=terminal; bounded (no infinite retry).

7. PROVIDER-WAIT branch: ABSENT.
   Zero `provider` hits in current server/app.py; no WAITING_PROVIDER state
   (contract TASK_STATES confirms). Workers call register/heartbeat/claim/
   result/artifacts only. Any provider-wait retry assumption is STALE —
   prior quota work (DLQ-05/T16-era) grounds on removed code.

8. MUSE resume/session-message (Mac only)
   Adapter supports resume under a verified session contract (same binding
   enforced, muse_adapter.py:45-72; foreign checkpoints quarantined,
   mac daemon.py:341-346). WHEN_SAFE=only under verified session_ref;
   this is session CONTINUATION, not a fresh attempt. Windows has no
   equivalent path. Asymmetry is guard-railed, not a hole.

## Gaps for the writer (not fixes — prep notes)

- G-C1: no idempotency/side-effect declaration exists on TaskPacket; rows
  2/3 cannot be made safe by mechanism until classification exists.
- G-C2: row 4 (Windows orphan) has no code-level mitigation on current disk.
- G-C3: row 7 — decide whether provider-wait removal is intentional; if so,
  retire DLQ-05-era docs/tests references.

---
§9 block: TASK_ID=MASTER-6C-RIK MATRIX-v1 STATUS=DONE (staged in-slot)
NEW_EVIDENCE=8-row matrix + headline rule + 3 writer gaps
FILES_READ=server/app.py (result/verify/resume/claim), integration_contract.py,
win+mac daemons, muse_adapter (MW1 grounding extended, deltas re-read)
REPORT_WRITTEN=runtime/slots/WIN-01/MASTER_6C_RETRY_MATRIX.md
BLOCKER=REPORT_ROOT delivery; shell (no live retry-path proof)
NEXT_SAFE_TASK=§6E IDLE/RESOURCE COST (shell-free static pass)

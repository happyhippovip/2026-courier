# MUSE-HNI-16 checkpoint — RESTART_RACE_WINDOW_QA (read-only)

TASK_ID=MUSE-HNI-16 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T13:34Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_16_RESTART_RACE_WINDOW_QA.claim.json (atomic).
REUSED: reclaim_stale app.py:416-454, /verify :466-515 (prior reads); cross-proc
residual (known, cited only).

SUBCASES (restart race windows, static; 0 executions, ledger untouched):
S1 Stale threshold 300s vs heartbeat 30s (daemon.py:369-376) = 10x margin; false
  quarantine needs 10 consecutive lost heartbeats. Verifier poll 5s
  (courier_verifier.py:151). Windows bounded. SOUND.
S2 Crash mid-/verify before save (:514): result stays RESULT_RECEIVED; verifier
  re-poll re-verifies, same verdict, idempotent advance. SOUND.
S3 Verifier crash after POST-200: re-poll hits RECONCILED + same result_id ->
  ACK_DUPLICATE early-return (:476-479) BEFORE index increment. No double
  advance. SOUND.
S4 Dual verifiers same task: serialized; loser sees RECONCILED -> ACK/409.
  SOUND single-proc (cross-proc residual cited, not repeated).
S5 Worker executing across quarantine: late result -> 409 (not DISPATCHED);
  ambiguity resolved fail-closed by design (:431-449). SOUND policy.
S6 reclaim scans plan steps, syncs tasks[] via lookup (:441-444); scan-vs-POST
  race serialized single-proc. SOUND with known residual.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-17 (failed execution).

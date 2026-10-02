# W5 — Proof-runner preflight checklist (static consolidation, read-only)

For the RC NEXT_ACTION=RUN_PHYSICAL_ACCEPTANCE_PROOF runner. No new claims —
each item points at prior static evidence (MUSE-45 T-reports + WIN-01 W-reports).
Own-slot harvest note, not an authoritative packet (no WRITE_SCOPE for packets/).

## Must resolve BEFORE starting the run (else the run measures the wrong thing)
1. ONE binder only: motor flask (127.0.0.1:8080) vs waitress (0.0.0.0:8080)
   conflict on :8080 — pick one path (T8 F-T8-1).
2. .venv_service must exist before motor/verifier install (only the server
   installer creates it) (T8 F-T8-3).
3. DECLARE THE MOTOR: API loop in server/app.py vs file motor
   courier_continue.py — the run must name which it proves (T12 Q-T12-2).
4. Task duration <300s OR land a heartbeat-during-execution fix first —
   else healthy long tasks self-quarantine mid-run (W3 L-W3-1, envelope
   600s vs threshold 300s, reaper live every 60s).
5. Stay logged on: AtLogon/HKCU persistence dies at logoff (T8 F-T8-2).

## Must know DURING the run (avoid misreading evidence)
6. Rejection blockers always read "...: no reason" (verifier never sends
   `reason`) — missing cause is a known gap, not new breakage (T12 Q-T12-1).
7. Quota locks are WORKER-granular (pools never populated) — a shared
   credential will NOT cross-block workers (T16 P-T16-1).
8. Crash test: external-effect crash MUST surface as AMBIGUOUS_CRASH ->
   HUMAN_REQUIRED quarantine — that IS the designed pass behavior (T14).
9. Watchdog behavior is untested (T10 G-T10-1) — watch the 3rd motor
   process live; its restart behavior has no deterministic coverage.
10. Decide per-slot job-log retention BEFORE the run — historically DONE
    jobs lack re-verifiable logs (VERIFY report).

## Structural greens (already established statically)
- Full result->verify->reconcile->replenish chain is USER_CONTINUE-free
  (T12). Retries bounded both sides (T12 Q-T12-3). Resume identity hygiene
  sound (T14). Process kills exact-owned except uninstall outlier (W1/W2).
- No shell in this session: every item above still needs its LIVE proof.

## Disposition
Harvest note only. No code/doc changes. Handoff to proof runner / writer.

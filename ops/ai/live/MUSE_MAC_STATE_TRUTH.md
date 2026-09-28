# MUSE MAC — Source-Truth State Hunt (code = Wahrheit)

BASE=bd539f18 (detached HEAD, 2026-09-28). Methode: nur lesend
(grep/AST-Evidenz + 1 reine Funktionsprüfung, kein Server, kein Port,
kein Prozess, kein physischer RUN). Peer-Result-Dateien NICHT editiert —
unten stehen exakte Korrekturtexte für den Owner. Kein Source-Fix:
Funde 1–3 sind doc-seitig; Fund 4 braucht Schema-Entscheid (Writer).

Kanonisch (server/app.py): POST /tasks/result → RESULT_RECEIVED (Z. 382),
Verifier PASS → RECONCILED (Z. 503–507). TASK_STATES in
scripts/integration_contract.py: QUEUED, DISPATCHED, RESULT_RECEIVED,
RECONCILED, FAILED_VERIFICATION, FAILED_TERMINAL, HUMAN_REQUIRED.
Sonst nichts.

## Subcase 1 — VALIDATED_PENDING_VERIFY ist erfunden (G233)
- Code: 0 Treffer im gesamten ausführbaren Repo (grep über *.py).
- Behauptung: ops/ai/wall_results/G233_result.md:9
  "Task marked `VALIDATED_PENDING_VERIFY`; verifier daemon picks up
  pending item on restart…" (MISSING=None).
- Wahrheit: Validate läuft inline vor save_state (app.py:376→410);
  danach heißt der State RESULT_RECEIVED; pending_verification (Z. 456–464)
  listet RESULT_RECEIVED. Kein Daemon-Pickup-Pfad existiert.
- Matrix-Paket S3-Zeile sagt inzwischen korrekt RESULT_RECEIVED —
  Korrekturrichtung ist damit bereits akzeptiert.
- Korrekturtext (G233:9): ersetzen durch "Result persists as
  RESULT_RECEIVED; verification via POST /tasks/verify; no intermediate
  state, no daemon pickup."

## Subcase 2 — READY-Rollback ist erfunden (G231)
- Code: 0 Treffer `"READY"` als Task-State in server/app.py.
- Behauptung: G231_result.md:9 "…task safely rolls back to `READY`
  for fresh attempt" (MISSING=None).
- Wahrheit: reclaim_stale (Z. 416–454) setzt DISPATCHED+L215-Stale-Worker
  auf HUMAN_REQUIRED + STALE_WORKER_EFFECT_AMBIGUOUS, Goal→BLOCKED,
  `reclaimed_tasks: 0` (wörtlich). Frischer Attempt erst nach
  POST resume→QUEUED→Claim (frische attempt/dispatch, Z. 327–331).
  Automatisches READY gibt es nicht.
- Korrekturtext (G231:9): "…task quarantined to HUMAN_REQUIRED
  (STALE_WORKER_EFFECT_AMBIGUOUS), goal BLOCKED; fresh attempt only via
  resume→QUEUED→claim."

## Subcase 3 — ABANDONED + Auto-READY + Auto-Increment erfunden (G237)
- Code: 0 Treffer ABANDONED in server/ + scripts/.
- Behauptung: G237_result.md:9 "attempt logged as `ABANDONED` and task
  returned to `READY` with attempt counter incremented."
- Wahrheit: drei Fehler in einem Satz — kein ABANDONED-Feld, kein
  READY (s. Subcase 2), kein Auto-Increment (attempts+1 erst im nächsten
  Claim nach Resume, Z. 329). Richtig ist nur die 300-s-last_seen-Schwelle
  (Z. 422–426).
- Korrekturtext (G237:9): "stale worker detected via 300s last_seen gap;
  task → HUMAN_REQUIRED (quarantine), goal BLOCKED; attempts unchanged
  until post-resume claim."

## Subcase 4 — Fehlende Timestamp-/Ordering-Felder (echte Code-Lücke)
- Geprüft per Funktionsausführung (kein Server): validate_durable_result
  liefert exakt 9 Felder (artifacts, attempt_id, dispatch_id, goal_id,
  result_id, run_id, status, task_id, worker_id) — kein Zeitfeld.
  Verification-Record (app.py:496–501): verifier_id, result_id, verdict,
  artifacts — kein Zeitfeld. Tasks tragen weder dispatched_at noch
  received_at; resume setzt resumed_from ohne Timestamp (Z. 537–540).
- Folge: result→verify→resume-Reihenfolge ist aus State allein nicht
  rekonstruierbar (nur Worker-last_seen-Heartbeats). Jede Evidence mit
  Zeitordnungs-Behauptung aus State überbehauptet (betrifft u. a. die
  "counter incremented"-Lesart in G237).
- Fix-Vorschlag (Writer, nicht ausgeführt): received_at/verified_at per
  time.time() in task_result + verify setzen; resumed_at in resume;
  Contract unberührt (Server-Stempel, kein Worker-Input). Kosmetik-Nebenfund:
  integration_contract.py artifact-Form-Tupel enthält denselben
  4er-Set zweimal (harmlos, keine Änderung).

## Addendum (2026-09-28, nach Write): Peer korrigiert live
- G233_result.md bereits per CORRECTION-Appendix auf RESULT_RECEIVED
  berichtigt (unberührt gelassen) → Subcase 1 SUPERSEDED_BY_PEER.
- Matrix-Paket S1–S9 komplett auf Code-Truth umgeschrieben
  (S2="State Impossible", S3=RESULT_RECEIVED, S7=HUMAN_REQUIRED,
  S9=ACK_DUPLICATE) → Matrix-Anteile SUPERSEDED_BY_PEER.
- Offen + eigenständig: G231/G237-Korrekturtexte (beide Dateien
  unverändert) sowie Subcase 4 (Timestamps, von niemandem angefasst).

DO_NOT_REPEAT_FINGERPRINT=musemac-state-truth-bd539f18-subcases1-4
NEXT=Writer-Entscheid zu Fund 4 + G231/G237-Korrekturen übernehmen.
